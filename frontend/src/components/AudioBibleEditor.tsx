import { useState } from 'react';
import { createAudioBible, updateAudioBible } from '../api/client.ts';
import type { AudioBible } from '../types.ts';
import { ErrorMessage } from './Status.tsx';
import './EntityManager.css';

interface AudioBibleEditorProps {
  seriesId: string;
  bible: AudioBible | null;
  onSaved: () => void;
}

const FIELDS: (keyof AudioBible)[] = [
  'voice_style',
  'narration_style',
  'dialogue_style',
  'music_style',
  'sound_effect_style',
  'ambient_style',
  'audio_notes',
];

export function AudioBibleEditor({ seriesId, bible, onSaved }: AudioBibleEditorProps) {
  const [values, setValues] = useState<Partial<AudioBible>>(bible ? { ...bible } : {});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (field: keyof AudioBible, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (bible) {
        await updateAudioBible(seriesId, values);
      } else {
        await createAudioBible(seriesId, values);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save audio bible');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="entity-manager">
      <h3>Audio Bible</h3>
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
          {bible ? 'Update Audio Bible' : 'Create Audio Bible'}
        </button>
      </form>
    </section>
  );
}
