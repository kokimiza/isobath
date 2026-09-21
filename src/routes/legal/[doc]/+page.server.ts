import { error } from '@sveltejs/kit';
import { marked } from 'marked';
import type { EntryGenerator, PageServerLoad } from './$types';

// Rendered at build time only (prerender): marked never ships to the browser.
// Japanese is the authoritative version of every document.
const sources = import.meta.glob<string>('/src/lib/content/legal/ja/*.md', {
	query: '?raw',
	import: 'default',
	eager: true,
});

const docs = new Map(
	Object.entries(sources).map(([file, md]) => [file.split('/').at(-1)!.replace(/\.md$/, ''), md]),
);

export const entries: EntryGenerator = () => [...docs.keys()].map((doc) => ({ doc }));

export const load: PageServerLoad = ({ params }) => {
	const md = docs.get(params.doc);
	if (!md) error(404);
	return {
		title: /^# (.+)$/m.exec(md)?.[1] ?? params.doc,
		// trusted, repository-authored content
		html: marked.parse(md, { async: false }),
	};
};
