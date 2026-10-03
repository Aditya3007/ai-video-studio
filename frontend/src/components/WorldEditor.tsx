import { useState } from 'react';
import { createWorld, updateWorld } from '../api/client.ts';
import type { World } from '../types.ts';
import { ErrorMessage } from './Status.tsx';
import './EntityManager.css';

interface WorldEditorProps {
  seriesId: string;
  world: World | null;
  onSaved: () => void;
}

const DEFAULT = {
  name: '',
  description: '',
  setting: '',
  era: '',
  current_era: '',
  geography: '',
  technology: '',
  rules: '',
  cultural_context: '',
  history_context: '',
  social_structure: '',
  timeline_notes: '',
};

export function WorldEditor({ seriesId, world, onSaved }: WorldEditorProps) {
  const [values, setValues] = useState<Partial<World>>(world ? { ...world } : DEFAULT);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (field: keyof World, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!values.name?.trim()) return;
    setSaving(true);
    setError(null);
    try {
      if (world) {
        await updateWorld(world.id, values);
      } else {
        await createWorld(seriesId, values);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save world');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="entity-manager">
      <h3>World</h3>
      {error && <ErrorMessage message={error} />}
      <form onSubmit={handleSubmit} className="entity-form">
        <label>
          Name
          <input
            value={values.name || ''}
            onChange={(e) => handleChange('name', e.target.value)}
            disabled={saving}
          />
        </label>
        {(
          [
            'description',
            'setting',
            'era',
            'current_era',
            'geography',
            'technology',
            'rules',
            'cultural_context',
            'history_context',
            'social_structure',
            'timeline_notes',
          ] as (keyof World)[]
        ).map((field) => (
          <label key={field}>
            {field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            <textarea
              value={(values[field] as string | undefined) || ''}
              onChange={(e) => handleChange(field, e.target.value)}
              disabled={saving}
            />
          </label>
        ))}
        <button type="submit" disabled={saving || !values.name?.trim()}>
          {world ? 'Update World' : 'Create World'}
        </button>
      </form>
    </section>
  );
}
