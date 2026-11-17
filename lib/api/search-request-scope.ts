/** One search owns the UI; replaced requests are cancelled and cannot commit. */
export class SearchRequestScope {
  private current: AbortController | null = null;
  begin(): AbortController {
    this.cancel();
    this.current = new AbortController();
    return this.current;
  }
  owns(request: AbortController): boolean {
    return this.current === request && !request.signal.aborted;
  }
  cancel(): void {
    this.current?.abort();
    this.current = null;
  }
}
