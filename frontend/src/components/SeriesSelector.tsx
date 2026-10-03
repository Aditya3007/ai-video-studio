import { useState } from 'react';
import type { Series, SeriesCreate } from '../types.ts';
import { ErrorMessage } from './Status.tsx';
import './SeriesSelector.css';

interface SeriesSelectorProps {
  seriesList: Series[];
  selectedId: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (id: string) => void;
  onCreate: (body: SeriesCreate) => Promise<void>;
}

export function SeriesSelector({
  seriesList,
  selectedId,
  loading,
  error,
  onSelect,
  onCreate,
}: SeriesSelectorProps) {
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      await onCreate({ name: name.trim() });
      setName('');
      setIsCreating(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create series');
    } finally {
      setCreating(false);
    }
  };

  if (loading) return <p className="status loading">Loading series…</p>;

  return (
    <aside className="series-selector">
      <h2>Series</h2>
      {error && <ErrorMessage message={error} />}
      {createError && <ErrorMessage message={createError} />}
      <ul className="series-list">
        {seriesList.map((series) => (
          <li key={series.id}>
            <button
              type="button"
              className={series.id === selectedId ? 'selected' : ''}
              onClick={() => onSelect(series.id)}
            >
              {series.name}
            </button>
          </li>
        ))}
      </ul>
      {seriesList.length === 0 && <p className="empty">No series yet.</p>}
      {isCreating ? (
        <form onSubmit={handleSubmit} className="inline-form">
          <label htmlFor="new-series-name">Name</label>
          <input
            id="new-series-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New series name"
            disabled={creating}
          />
          <div className="form-actions">
            <button type="submit" disabled={!name.trim() || creating}>
              Create
            </button>
            <button
              type="button"
              onClick={() => {
                setIsCreating(false);
                setName('');
                setCreateError(null);
              }}
              disabled={creating}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button type="button" onClick={() => setIsCreating(true)}>
          + New Series
        </button>
      )}
    </aside>
  );
}
