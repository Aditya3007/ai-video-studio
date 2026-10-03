import type { ReactNode } from 'react';
import { useState } from 'react';
import { ErrorMessage } from './Status.tsx';
import './EntityManager.css';

interface BaseEntity {
  id: string;
  name: string;
}

interface EntityManagerProps<T extends BaseEntity> {
  title: string;
  entities: T[];
  emptyMessage: string;
  defaultValues: Partial<T>;
  renderForm: (
    values: Partial<T>,
    onChange: (next: Partial<T>) => void,
    saving: boolean
  ) => ReactNode;
  onSave: (values: Partial<T>) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

export function EntityManager<T extends BaseEntity>(props: EntityManagerProps<T>) {
  const [editing, setEditing] = useState<Partial<T>>(props.defaultValues);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = (entity: T) => setEditing(entity);
  const handleChange = (next: Partial<T>) => setEditing((prev) => ({ ...prev, ...next }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await props.onSave(editing);
      setEditing(props.defaultValues);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure?')) return;
    setError(null);
    try {
      await props.onDelete(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  return (
    <section className="entity-manager">
      <h3>{props.title}</h3>
      {error && <ErrorMessage message={error} />}
      {props.entities.length === 0 ? (
        <p className="empty">{props.emptyMessage}</p>
      ) : (
        <ul className="entity-list">
          {props.entities.map((entity) => (
            <li key={entity.id}>
              <span className="entity-name">{entity.name}</span>
              <div className="entity-actions">
                <button type="button" onClick={() => startEdit(entity)} disabled={saving}>
                  Edit
                </button>
                <button type="button" onClick={() => handleDelete(entity.id)} disabled={saving}>
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={handleSubmit} className="entity-form">
        {props.renderForm(editing, handleChange, saving)}
        <button type="submit" disabled={saving}>
          {editing.id ? 'Update' : 'Create'}
        </button>
      </form>
    </section>
  );
}
