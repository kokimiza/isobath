import { expect, test, type Page } from '@playwright/test';

const versions = { terms: '1', privacy: '2', research: '2' };
const nextUpdate = '2030-09-22T16:00:00Z';
const stage = (charted: boolean) => ({
	stage: charted ? 'CHARTED' : 'COLLECTING',
	version: 'test',
});

/** Posterior of a lone respondent: wide and split in two, as the batch reports it. */
function soloPlacement() {
	const bins = 32;
	const edges = Array.from({ length: bins + 1 }, (_, i) => -3 + (6 * i) / bins);
	const mid = edges.slice(0, -1).map((e) => e + 3 / bins);
	const bump = (x: number, y: number, cx: number, cy: number) =>
		Math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / 0.8);
	const raw = mid.flatMap((x) =>
		mid.map((y) => bump(x, y, -0.9, 0.3) + 0.6 * bump(x, y, 1.1, -0.4)),
	);
	const total = raw.reduce((a, b) => a + b);
	return {
		position: [-0.15, 0.05],
		se: Array<number>(16).fill(0.9),
		confidence: 0.45,
		credible_region: {
			kind: 'grid_hpd',
			edges: [edges, edges],
			bins,
			cell_probability: raw.map((v) => v / total),
			mass: 0.95,
			probability: 0.95,
		},
		unmatched: { alignment_unmatched: 0, unseen: 0.2, total: 0.2 },
		inference_mode: 'cut',
		at: '2030-09-21T16:00:00Z',
	};
}

const session = {
	access_token: 'test-access-token',
	refresh_token: 'test-refresh-token',
	token_type: 'bearer',
	expires_in: 36000,
	expires_at: Math.floor(Date.now() / 1000) + 36000,
	user: {
		id: '6ab3ccf8-531f-4e48-bf07-5db3441d7e80',
		aud: 'authenticated',
		role: 'authenticated',
		email: 'test@example.com',
		app_metadata: {},
		user_metadata: {},
		created_at: '2026-01-01T00:00:00Z',
	},
};

async function setup(
	page: Page,
	{
		loggedIn = true,
		consented = false,
		failConsent = false,
		claimedAtSignup = false,
		initialCompleted = false,
		doneToday = false,
		surveyReady = true,
		charted = false,
		registrationPending = false,
	} = {},
) {
	const stored = structuredClone(session);
	if (claimedAtSignup) stored.user.user_metadata = { consents: { terms: '1', privacy: '2' } };
	if (loggedIn)
		await page.addInitScript((value) => {
			localStorage.setItem('sb-127-auth-token', JSON.stringify(value));
		}, stored);
	await page.route('http://127.0.0.1:18001/**', async (route) => {
		if (route.request().url().includes('/token')) await route.fulfill({ json: stored });
		else if (route.request().url().includes('/signup')) {
			registrationPending = true;
			await route.fulfill({ json: stored });
		} else await route.fulfill({ json: stored.user });
	});
	const writes: unknown[] = [];
	let initialOpen = false;
	let consentFailures = failConsent ? 1 : 0;
	await page.route('http://127.0.0.1:18000/**', async (route) => {
		const request = route.request();
		const path = new URL(request.url()).pathname;
		const json = (value: unknown, status = 200) => route.fulfill({ status, json: value });
		switch (path) {
			case '/v1/me/registration':
				writes.push(request.postDataJSON());
				registrationPending = false;
				consented = true;
				return route.fulfill({ status: 204 });
			case '/v1/meta':
				return json({
					chart: stage(charted),
					participants: charted ? 1 : 0,
					consent_versions: versions,
					consent_required: ['terms', 'privacy'],
					updated_at: null,
					next_update_at: nextUpdate,
					survey_write_enabled: true,
					signup_enabled: true,
				});
			case '/v1/chart/current':
				if (!charted) return json({ error: { code: 'chart_not_ready' } }, 404);
				// one respondent: every cell is below k and suppressed
				return json({
					chart: stage(true),
					updated_at: null,
					next_update_at: nextUpdate,
					map: {
						bins: 24,
						extent: [-3, 3, -3, 3],
						k: 10,
						counts: Array.from({ length: 24 }, () => Array<number>(24).fill(0)),
					},
				});
			case '/v1/me/consents':
				if (request.method() === 'POST') {
					writes.push(request.postDataJSON());
					consented = true;
					return route.fulfill({ status: 204 });
				}
				if (consentFailures-- > 0) return json({ error: { code: 'internal_error' } }, 500);
				return json({
					required: { terms: '1', privacy: '2' },
					versions,
					complete: consented && !registrationPending,
					registration_required: registrationPending,
					research: false,
				});
			case '/v1/me/position':
				return json({
					chart: stage(charted),
					observer_no: 1,
					participants: charted ? 1 : 0,
					survey: {
						initial_completed: initialCompleted,
						open_session: initialOpen,
						open_kind: initialOpen ? 'initial' : null,
						continuous_done_today: doneToday,
					},
					updated_at: null,
					next_update_at: nextUpdate,
					...(charted ? soloPlacement() : {}),
				});
			case '/v1/me/history':
				return json({ items: [], next_cursor: null });
			case '/v1/me/surveys':
				if (!surveyReady) return json({ error: { code: 'survey_not_ready' } }, 503);
				if ((request.postDataJSON() as { kind: string }).kind === 'continuous' && !initialCompleted)
					return json({ error: { code: 'initial_required' } }, 409);
				initialOpen = true;
				return json(
					{ id: 'survey-1', kind: 'initial', status: 'open', total: 100, answered: 0 },
					201,
				);
			case '/v1/me/surveys/current':
				return json({
					id: 'survey-1',
					kind: 'initial',
					status: 'open',
					total: 100,
					answered: 0,
					questions: [{ id: 1, text: '新しい考えに興味を持つ' }],
				});
			default:
				throw new Error(`Unexpected API request: ${request.method()} ${path}`);
		}
	});
	return writes;
}

test('unpublished question bank explains readiness and keeps a way back', async ({ page }) => {
	await setup(page, { consented: true, surveyReady: false });
	await page.goto('/survey/initial');
	await expect(page.getByRole('status')).toContainText('初回測深の質問は、現在準備中です。');
	await expect(page.getByRole('button', { name: /^1/ })).toHaveCount(0);
	await page.getByRole('link', { name: 'マイページへ', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'マイページ', exact: true })).toBeVisible();
});

test('first visit reaches consent, then dashboard, history and settings without a loading trap', async ({
	page,
}) => {
	const writes = await setup(page);
	await page.goto('/');
	await page.getByRole('link', { name: 'マイページへ', exact: true }).click();
	await expect(page.getByRole('heading', { name: '参加への同意' })).toBeVisible();
	const checkboxes = page.getByRole('checkbox');
	for (let i = 0; i < 4; i++) await checkboxes.nth(i).check();
	await page.getByRole('button', { name: '同意して進む' }).click();
	await expect(page.getByRole('heading', { name: 'マイページ', exact: true })).toBeVisible();
	expect(writes).toEqual([
		{
			consents: [
				{ document: 'terms', version: '1' },
				{ document: 'privacy', version: '2' },
			],
		},
	]);
	await page
		.getByRole('navigation', { name: 'マイページ' })
		.getByRole('link', { name: '航跡（変化の記録）' })
		.click();
	await expect(page.getByText('まだ航跡はありません。', { exact: false })).toBeVisible();
	await page
		.getByRole('navigation', { name: 'マイページ' })
		.getByRole('link', { name: '設定', exact: true })
		.click();
	await expect(page.getByRole('button', { name: 'ログアウト' })).toBeVisible();
	await page.getByRole('link', { name: '回答・現在地', exact: true }).click();
	await page.getByRole('link', { name: '初回測深を始める', exact: true }).click();
	await expect(page.getByText('新しい考えに興味を持つ')).toBeVisible();
});

test('uncharted chart and footer lead a signed-in user straight to questions', async ({ page }) => {
	await setup(page, { consented: true });
	await page.goto('/chart');
	await expect(page.getByText('最初の推定の前', { exact: true })).toBeVisible();
	await page.getByRole('link', { name: '初回測深を始める', exact: true }).click();
	await expect(page.getByText('新しい考えに興味を持つ')).toBeVisible();
	await page.goto('/chart');
	await page.getByRole('contentinfo').getByRole('link', { name: '測深に参加する' }).click();
	await expect(page.getByText('新しい考えに興味を持つ')).toBeVisible();
	await expect(page.getByLabel('メールアドレス')).toHaveCount(0);
});

test('direct signup URL reuses the signed-in session', async ({ page }) => {
	await setup(page, { consented: true });
	await page.goto('/auth/signup');
	await expect(page.getByText('新しい考えに興味を持つ')).toBeVisible();
	await expect(page.getByLabel('メールアドレス')).toHaveCount(0);
});

test('anonymous participation opens the pre-account questions before any login', async ({
	page,
}) => {
	await setup(page, { loggedIn: false });
	for (const [from, link] of [
		['/', '測深に参加する'],
		['/chart', '質問に回答する'],
	]) {
		await page.goto(from);
		await page.getByRole('main').getByRole('link', { name: link, exact: true }).first().click();
		await expect(page).toHaveURL(/\/auth\/signup\?next=%2Fsurvey$/);
		await expect(page.getByLabel('生まれた年（西暦）')).toBeVisible();
	}
	await page.goto('/profile');
	await expect(page).toHaveURL(/\/auth\/login\?next=%2Fprofile$/);
	await page.goto('/auth/signup?next=%2Fsurvey');
	await page.getByRole('main').getByRole('link', { name: 'ログイン', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'ログイン', exact: true })).toBeVisible();
	await page.getByText('メールアドレスとパスワードを使う', { exact: true }).click();
	await page.getByLabel('メールアドレス').fill('test@example.com');
	await page.getByLabel('パスワード', { exact: true }).fill('test-password');
	await page.getByRole('button', { name: 'ログイン', exact: true }).click();
	await expect(page.getByRole('heading', { name: '参加への同意' })).toBeVisible();
	await expect(page).toHaveURL(/\/consent\?next=%2Fsurvey$/);
});

test('signup consent metadata is recorded on first visit without asking again', async ({
	page,
}) => {
	const writes = await setup(page, { claimedAtSignup: true });
	await page.goto('/profile');
	await expect(page.getByRole('heading', { name: 'マイページ', exact: true })).toBeVisible();
	expect(writes).toHaveLength(1);
});

test('consent API failure shows a retry that recovers', async ({ page }) => {
	await setup(page, { consented: true, failConsent: true });
	await page.goto('/profile');
	await expect(page.getByRole('alert')).toBeVisible();
	await page.getByRole('link', { name: '再試行', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'マイページ', exact: true })).toBeVisible();
});

test('account settings are accessible before consent', async ({ page }) => {
	await setup(page);
	await page.goto('/settings');
	await expect(page.getByRole('button', { name: 'ログアウト' })).toBeVisible();
	await page.getByRole('link', { name: '回答・現在地', exact: true }).click();
	await expect(page.getByRole('heading', { name: '参加への同意' })).toBeVisible();
});

test('a completed daily survey is shown as completed on the uncharted chart', async ({ page }) => {
	await setup(page, { consented: true, initialCompleted: true, doneToday: true });
	await page.goto('/chart');
	await expect(page.getByText('今日の継続測深は完了しています。', { exact: true })).toBeVisible();
	await expect(page.getByRole('link', { name: '初回測深を始める', exact: true })).toHaveCount(0);
});

test('signup requires birth month and a gender choice, including prefer not to say', async ({
	page,
}) => {
	const writes = await setup(page, { loggedIn: false });
	await page.goto('/auth/signup?next=%2Fsurvey');
	await expect(page.getByRole('heading', { name: '測深に参加する' })).toBeVisible();
	for (let i = 0; i < 4; i++) await page.getByRole('checkbox').nth(i).check();
	await page.getByRole('button', { name: '登録方法を選ぶ' }).click();
	await expect(page).toHaveURL(/auth\/signup/);
	await page.getByLabel('生まれた年（西暦）').fill('2000');
	await page.getByLabel('生まれた月', { exact: true }).selectOption('8');
	await page.getByRole('button', { name: '登録方法を選ぶ' }).click();
	await expect(page).toHaveURL(/auth\/signup/);
	await page.getByLabel('回答したくない', { exact: true }).check();
	await page.getByRole('button', { name: '登録方法を選ぶ' }).click();
	await expect(page).toHaveURL(/auth\/register/);
	await expect(page.getByRole('button', { name: 'Googleで登録する' })).toBeVisible();
	await page.getByText('メールアドレスとパスワードを使う', { exact: true }).click();
	await page.getByLabel('メールアドレス').fill('new@example.com');
	await page.getByLabel('パスワード', { exact: true }).fill('test-password');
	const signupRequest = page.waitForRequest(
		(r) => r.url().includes('/signup') && r.method() === 'POST',
	);
	await page.getByRole('button', { name: '登録する', exact: true }).click();
	const signupBody = (await signupRequest).postDataJSON() as {
		data: { research_demographics: unknown };
	};
	expect(signupBody.data?.research_demographics).toBeUndefined();
	await expect(page.getByText('新しい考えに興味を持つ')).toBeVisible();
	expect(await page.evaluate(() => sessionStorage.getItem('isobath:registration'))).toBeNull();
	expect(writes).toEqual([
		{
			birth_year: 2000,
			birth_month: 8,
			gender: 'prefer_not_to_say',
			adult_confirmed: true,
			non_diagnostic_confirmed: true,
			consents: [
				{ document: 'terms', version: '1' },
				{ document: 'privacy', version: '2' },
			],
		},
	]);
});

test('mobile chart keeps the survey entry and localized consent destination', async ({ page }) => {
	await setup(page);
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/chart');
	const start = page.getByRole('link', { name: '初回測深を始める', exact: true });
	await expect(start).toBeVisible();
	await page.screenshot({ path: test.info().outputPath('chart-mobile.png'), fullPage: true });
	expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
	await page.goto('/en/chart');
	await page.getByRole('link', { name: 'Start the initial survey', exact: true }).click();
	await expect(page).toHaveURL(/\/en\/consent\?next=%2Fen%2Fsurvey%2Finitial$/);
	await expect(page.getByRole('checkbox')).toHaveCount(5);
});

test('registration demographics stay readable on mobile and in English', async ({ page }) => {
	await setup(page, { loggedIn: false });
	await page.goto('/auth/signup');
	await expect(page.getByRole('radio')).toHaveCount(4);
	await expect(page.locator('input[type="date"]')).toHaveCount(0);
	await page.screenshot({ path: test.info().outputPath('signup-desktop.png'), fullPage: true });
	await page.setViewportSize({ width: 390, height: 844 });
	await page.screenshot({ path: test.info().outputPath('signup-mobile.png'), fullPage: true });
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
	await page.goto('/en/auth/signup');
	await expect(page.getByLabel('Birth year', { exact: true })).toBeVisible();
	await expect(page.getByLabel('Prefer not to say', { exact: true })).toBeVisible();
});

async function prepareRegistration(page: Page) {
	await page.goto('/auth/signup?next=%2Fsurvey');
	await page.getByLabel('生まれた年（西暦）').fill('2000');
	await page.getByLabel('生まれた月', { exact: true }).selectOption('8');
	await page.getByLabel('回答したくない', { exact: true }).check();
	for (let i = 0; i < 4; i++) await page.getByRole('checkbox').nth(i).check();
	await page.getByRole('button', { name: '登録方法を選ぶ' }).click();
	await expect(page).toHaveURL(/auth\/register/);
}

test('Google callback completes the draft once without sending research fields to OAuth', async ({
	page,
}) => {
	const writes = await setup(page, { loggedIn: false, registrationPending: true });
	let authorize: URL | undefined;
	await page.route('**/authorize?**', async (route) => {
		authorize = new URL(route.request().url());
		await route.fulfill({
			status: 302,
			headers: { location: 'http://localhost:4173/auth/callback?code=test-code&next=%2Fsurvey' },
		});
	});
	await prepareRegistration(page);
	await page.screenshot({ path: test.info().outputPath('methods-desktop.png'), fullPage: true });
	await page.setViewportSize({ width: 390, height: 844 });
	await page.screenshot({ path: test.info().outputPath('methods-mobile.png'), fullPage: true });
	await page.getByRole('button', { name: 'Googleで登録する' }).click();
	await expect(page.getByText('新しい考えに興味を持つ')).toBeVisible();
	expect(authorize?.searchParams.get('provider')).toBe('google');
	expect(authorize?.searchParams.has('code_challenge')).toBe(true);
	expect(authorize?.href).not.toMatch(/birth_year|gender|2000/);
	expect(writes).toHaveLength(1);
	expect(await page.evaluate(() => sessionStorage.getItem('isobath:registration'))).toBeNull();
});

test('missing draft after authentication recovers through the registration form', async ({
	page,
}) => {
	const writes = await setup(page, { registrationPending: true });
	await page.goto('/survey');
	await expect(page).toHaveURL(/consent/);
	await page.getByLabel('生まれた年（西暦）').fill('2000');
	await page.getByLabel('生まれた月', { exact: true }).selectOption('8');
	await page.getByLabel('女性', { exact: true }).check();
	for (let i = 0; i < 4; i++) await page.getByRole('checkbox').nth(i).check();
	await page.getByRole('button', { name: '同意して進む' }).click();
	await expect(page.getByText('新しい考えに興味を持つ')).toBeVisible();
	expect(writes).toHaveLength(1);
});

test('authentication chooser without a draft returns to the independent preparation page', async ({
	page,
}) => {
	await setup(page, { loggedIn: false });
	await page.goto('/auth/register?next=%2Fsurvey');
	await expect(page).toHaveURL(/auth\/signup\?next=%2Fsurvey/);
	await expect(page.getByLabel('メールアドレス')).toHaveCount(0);
});

test('email confirmation callback preserves the preparation draft and completes registration', async ({
	page,
}) => {
	const writes = await setup(page, { loggedIn: false, registrationPending: true });
	await page.route('http://127.0.0.1:18001/auth/v1/signup*', (route) =>
		route.fulfill({ json: session.user }),
	);
	await prepareRegistration(page);
	await page.getByText('メールアドレスとパスワードを使う', { exact: true }).click();
	await page.getByLabel('メールアドレス').fill('new@example.com');
	await page.getByLabel('パスワード', { exact: true }).fill('test-password');
	await page.getByRole('button', { name: '登録する', exact: true }).click();
	await expect(page.getByRole('status')).toBeVisible();
	expect(await page.evaluate(() => sessionStorage.getItem('isobath:registration'))).not.toBeNull();
	await page.goto('/auth/callback?code=test-code&next=%2Fsurvey');
	await expect(page.getByText('新しい考えに興味を持つ')).toBeVisible();
	expect(writes).toHaveLength(1);
	expect(await page.evaluate(() => sessionStorage.getItem('isobath:registration'))).toBeNull();
});

test('a lone respondent sees their position with its isobaths, and no regions', async ({
	page,
}) => {
	await setup(page, { consented: true, initialCompleted: true, charted: true });
	await page.goto('/chart');
	const map = page.getByRole('img', { name: /人格海図の密度/ });
	await expect(map.locator('circle')).toHaveCount(1);
	// 95/80/50%: two separated modes stay two rings at the tighter levels
	const isobaths = map.locator('path');
	await expect(isobaths).toHaveCount(3);
	for (const d of await isobaths.evaluateAll((p) => p.map((e) => e.getAttribute('d') ?? '')))
		expect(d).toMatch(/^M[\d.]+,[\d.]+L/);
	await expect(page.getByText('点のまわりの等深線', { exact: false })).toBeVisible();
	await expect(page.getByText('この海の地形は、これから。')).toHaveCount(0);

	await page.goto('/profile');
	await expect(page.getByText('推定済みの海図', { exact: true })).toBeVisible();
	await expect(page.getByText('公開中の海図を固定したうえで', { exact: false })).toBeVisible();
	await expect(
		page.getByText('複数の海域に分かれているとはまだ言えない', { exact: false }),
	).toBeVisible();
});
