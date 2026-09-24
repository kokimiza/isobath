/** Stop waiting without pretending that an already-sent write was rolled back. */
export function until<T>(promise: PromiseLike<T>, signal: AbortSignal): Promise<T> {
	return new Promise((resolve, reject) => {
		const abort = () => reject(signal.reason as Error);
		if (signal.aborted) reject(signal.reason as Error);
		else signal.addEventListener('abort', abort, { once: true });
		Promise.resolve(promise)
			.then(resolve, reject)
			.finally(() => signal.removeEventListener('abort', abort));
	});
}
