import { useState } from 'react';
import { createVisualBible, updateVisualBible } from '../api/client.ts';
import type { VisualBible } from '../types.ts';
import { ErrorMessage } from './Status.tsx';
import './EntityManager.css';

interface VisualBibleEditorProps {
  seriesId: string;
  bible: VisualBible | null;
  onSaved: () => void;
}

const FIELDS: (keyof VisualBible)[] = [
  'art_style',
  'color_palette',
  'lighting_style',
  'camera_style',
  'lens_style',
  'composition_style',
  'environment_style',
  'character_rendering_style',
  'aspect_ratio',
  'visual_notes',
];

export function VisualBibleEditor({ seriesId, bible, onSaved }: VisualBibleEditorProps) {
  const [values, setValues] = useState<Partial<VisualBible>>(bible ? { ...bible } : {});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (field: keyof VisualBible, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (bible) {
        await updateVisualBible(seriesId, values);
      } else {
        await createVisualBible(seriesId, values);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save visual bible');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="entity-manager">
      <h3>Visual Bible</h3>
      {error && <ErrorMessage message={error} />}
      <form onSubmit={handleSubmit} className="entity-form">
        {FIELDS.map((field) => (
          <label key={field}>
            {field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            <input
              value={(values[field] as string | undefined) || ''}
              onChange={(e) => handleChange(field, e.target.value)}
              disabled={saving}
            />
          </label>
        ))}
        <button type="submit" disabled={saving}>
          {bible ? 'Update Visual Bible' : 'Create Visual Bible'}
        </button>
      </form>
    </section>
  );
}
