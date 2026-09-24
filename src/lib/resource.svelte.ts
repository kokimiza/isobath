import { onDestroy } from 'svelte';
import { apiErrorMessage } from './api.svelte';

/** Component-owned reads: keep successful data, cancel old work, and allow retry. */
export function resource<T>(read: (signal: AbortSignal) => Promise<T>) {
	class Resource {
		data = $state<T | null>(null);
		error = $state<string | null>(null);
		pending = $state(false);
		settled = $state(false);
		private controller: AbortController | undefined;
		private disposed = false;
		async load(): Promise<T | undefined> {
			if (this.disposed) return;
			this.controller?.abort();
			const controller = this.controller = new AbortController();
			this.pending = true;
			this.error = null;
			try {
				const data = await read(controller.signal);
				if (!controller.signal.aborted) { this.data = data; return data; }
			} catch (error) {
				if (!controller.signal.aborted) this.error = apiErrorMessage(error);
			} finally {
				if (!controller.signal.aborted) { this.pending = false; this.settled = true; }
			}
		}
		cancel() { this.controller?.abort(); this.pending = false; }
		dispose() { this.disposed = true; this.cancel(); }
	}
	const result = new Resource();
	onDestroy(() => result.dispose());
	return result;
}
