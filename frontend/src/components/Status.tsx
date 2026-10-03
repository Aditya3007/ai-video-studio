import './Status.css';

export function Loading() {
  return <p className="status loading">Loading…</p>;
}

export function ErrorMessage({ message }: { message: string }) {
  return <p className="status error">{message}</p>;
}

export function Empty({ message }: { message: string }) {
  return <p className="status empty">{message}</p>;
}
