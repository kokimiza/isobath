/** Stop waiting without pretending that an already-sent write was rolled back. */
export function until<T>(promise: PromiseLike<T>, signal: AbortSignal): Promise<T> {
	return new Promise((resolve, reject) => {
		const abort = () => reject(signal.reason);
		if (signal.aborted) reject(signal.reason);
		else signal.addEventListener('abort', abort, { once: true });
		Promise.resolve(promise).then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
	});
}

export const bounded = <T>(promise: PromiseLike<T>) => until(promise, AbortSignal.timeout(90_000));
