import { useCallback, useEffect, useState } from 'react';
import {
  createCharacter,
  createLocation,
  createObject,
  deleteCharacter,
  deleteLocation,
  deleteObject,
  getUniverse,
  listSeries,
  createSeries,
  updateCharacter,
  updateLocation,
  updateObject,
} from '../api/client.ts';
import type {
  Character,
  Location,
  Series,
  SeriesCreate,
  StoryObject,
  UniverseContext,
} from '../types.ts';
import { AudioBibleEditor } from './AudioBibleEditor.tsx';
import { EntityManager } from './EntityManager.tsx';
import { ErrorMessage, Loading } from './Status.tsx';
import { SeriesSelector } from './SeriesSelector.tsx';
import { StoryWorkspace } from './StoryWorkspace.tsx';
import { UnitEconomicsDashboard } from './UnitEconomicsDashboard.tsx';
import { VisualBibleEditor } from './VisualBibleEditor.tsx';
import { WorldEditor } from './WorldEditor.tsx';
import './Studio.css';

type Tab = 'overview' | 'story' | 'characters' | 'locations' | 'objects' | 'economics';

export function Studio() {
  const [seriesList, setSeriesList] = useState<Series[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [universe, setUniverse] = useState<UniverseContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('overview');

  const loadSeries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await listSeries();
      setSeriesList(items);
      if (items.length > 0) {
        setSelectedId((prev) => prev ?? items[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load series');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadUniverse = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    setUniverse(null);
    try {
      const ctx = await getUniverse(id);
      setUniverse(ctx);
    } catch (err) {
      setUniverse(null);
      setError(err instanceof Error ? err.message : 'Failed to load universe');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadSeries();
  }, [loadSeries]);

  useEffect(() => {
    if (selectedId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadUniverse(selectedId);
    }
  }, [selectedId, loadUniverse]);

  const handleCreateSeries = async (body: SeriesCreate) => {
    setError(null);
    const created = await createSeries(body);
    await loadSeries();
    setSelectedId(created.id);
  };

  const selectedSeries = seriesList.find((s) => s.id === selectedId);

  return (
    <div className="studio">
      <SeriesSelector
        seriesList={seriesList}
        selectedId={selectedId}
        loading={loading && seriesList.length === 0}
        error={error}
        onSelect={setSelectedId}
        onCreate={handleCreateSeries}
      />
      <main className="studio-workspace">
        {selectedSeries ? (
          <>
            <header className="series-header">
              <h1>{selectedSeries.name}</h1>
              <p className="series-meta">
                {selectedSeries.genre || 'No genre'} · {selectedSeries.language}
              </p>
            </header>
            {universe && (
              <nav className="tabs" aria-label="Series sections">
                {(
                  [
                    ['overview', 'Overview'],
                    ['story', 'Story'],
                    ['characters', 'Characters'],
                    ['locations', 'Locations'],
                    ['objects', 'Objects'],
                    ['economics', 'Economics'],
                  ] as [Tab, string][]
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    className={tab === key ? 'active' : ''}
                    onClick={() => setTab(key)}
                  >
                    {label}
                  </button>
                ))}
              </nav>
            )}
            {loading && !universe && <Loading />}
            {error && universe === null && <ErrorMessage message={error} />}
            {universe && (
              <section className="tab-panel">
                {tab === 'overview' && (
                  <OverviewPanel
                    seriesId={selectedSeries.id}
                    universe={universe}
                    onRefresh={() => loadUniverse(selectedSeries.id)}
                  />
                )}
                {tab === 'story' && (
                  <StoryWorkspace key={selectedSeries.id} seriesId={selectedSeries.id} />
                )}
                {tab === 'characters' && (
                  <EntityManager<Character>
                    title="Characters"
                    entities={universe.characters}
                    emptyMessage="No characters defined."
                    defaultValues={{
                      name: '',
                      description: '',
                      personality: '',
                      role: '',
                      voice_reference: '',
                    }}
                    renderForm={(values, onChange, saving) => (
                      <>
                        <label>
                          Name
                          <input
                            value={values.name || ''}
                            onChange={(e) => onChange({ name: e.target.value })}
                            disabled={saving}
                            required
                          />
                        </label>
                        <label>
                          Description
                          <textarea
                            value={values.description || ''}
                            onChange={(e) => onChange({ description: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                        <label>
                          Personality
                          <textarea
                            value={values.personality || ''}
                            onChange={(e) => onChange({ personality: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                        <label>
                          Role
                          <input
                            value={values.role || ''}
                            onChange={(e) => onChange({ role: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                        <label>
                          Voice reference
                          <input
                            value={values.voice_reference || ''}
                            onChange={(e) => onChange({ voice_reference: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                      </>
                    )}
                    onSave={async (values) => {
                      if (values.id) {
                        await updateCharacter(selectedSeries.id, values.id, values);
                      } else {
                        await createCharacter(selectedSeries.id, values);
                      }
                      await loadUniverse(selectedSeries.id);
                    }}
                    onDelete={async (id) => {
                      await deleteCharacter(selectedSeries.id, id);
                      await loadUniverse(selectedSeries.id);
                    }}
                  />
                )}
                {tab === 'locations' && (
                  <EntityManager<Location>
                    title="Locations"
                    entities={universe.locations}
                    emptyMessage="No locations defined."
                    defaultValues={{
                      name: '',
                      description: '',
                      location_type: '',
                      atmosphere: '',
                      visual_characteristics: '',
                    }}
                    renderForm={(values, onChange, saving) => (
                      <>
                        <label>
                          Name
                          <input
                            value={values.name || ''}
                            onChange={(e) => onChange({ name: e.target.value })}
                            disabled={saving}
                            required
                          />
                        </label>
                        <label>
                          Description
                          <textarea
                            value={values.description || ''}
                            onChange={(e) => onChange({ description: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                        <label>
                          Type
                          <input
                            value={values.location_type || ''}
                            onChange={(e) => onChange({ location_type: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                        <label>
                          Atmosphere
                          <textarea
                            value={values.atmosphere || ''}
                            onChange={(e) => onChange({ atmosphere: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                        <label>
                          Visual characteristics
                          <textarea
                            value={values.visual_characteristics || ''}
                            onChange={(e) => onChange({ visual_characteristics: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                      </>
                    )}
                    onSave={async (values) => {
                      if (values.id) {
                        await updateLocation(selectedSeries.id, values.id, values);
                      } else {
                        await createLocation(selectedSeries.id, values);
                      }
                      await loadUniverse(selectedSeries.id);
                    }}
                    onDelete={async (id) => {
                      await deleteLocation(selectedSeries.id, id);
                      await loadUniverse(selectedSeries.id);
                    }}
                  />
                )}
                {tab === 'objects' && (
                  <EntityManager<StoryObject>
                    title="Story Objects"
                    entities={universe.objects}
                    emptyMessage="No objects defined."
                    defaultValues={{ name: '', description: '', object_type: '', significance: '' }}
                    renderForm={(values, onChange, saving) => (
                      <>
                        <label>
                          Name
                          <input
                            value={values.name || ''}
                            onChange={(e) => onChange({ name: e.target.value })}
                            disabled={saving}
                            required
                          />
                        </label>
                        <label>
                          Description
                          <textarea
                            value={values.description || ''}
                            onChange={(e) => onChange({ description: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                        <label>
                          Type
                          <input
                            value={values.object_type || ''}
                            onChange={(e) => onChange({ object_type: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                        <label>
                          Significance
                          <textarea
                            value={values.significance || ''}
                            onChange={(e) => onChange({ significance: e.target.value })}
                            disabled={saving}
                          />
                        </label>
                      </>
                    )}
                    onSave={async (values) => {
                      if (values.id) {
                        await updateObject(selectedSeries.id, values.id, values);
                      } else {
                        await createObject(selectedSeries.id, values);
                      }
                      await loadUniverse(selectedSeries.id);
                    }}
                    onDelete={async (id) => {
                      await deleteObject(selectedSeries.id, id);
                      await loadUniverse(selectedSeries.id);
                    }}
                  />
                )}
                {tab === 'economics' && <UnitEconomicsDashboard seriesId={selectedSeries.id} />}
              </section>
            )}
          </>
        ) : (
          <p className="empty-workspace">Select or create a series to start.</p>
        )}
      </main>
    </div>
  );
}

function OverviewPanel({
  seriesId,
  universe,
  onRefresh,
}: {
  seriesId: string;
  universe: UniverseContext;
  onRefresh: () => void;
}) {
  return (
    <div className="overview">
      <WorldEditor
        key={universe.world ? universe.world.id : 'new'}
        seriesId={seriesId}
        world={universe.world}
        onSaved={onRefresh}
      />
      <VisualBibleEditor
        key={universe.visual_bible ? universe.visual_bible.id : 'new'}
        seriesId={seriesId}
        bible={universe.visual_bible}
        onSaved={onRefresh}
      />
      <AudioBibleEditor
        key={universe.audio_bible ? universe.audio_bible.id : 'new'}
        seriesId={seriesId}
        bible={universe.audio_bible}
        onSaved={onRefresh}
      />
      {universe.timeline && (
        <section className="entity-manager">
          <h3>Timeline</h3>
          <dl className="timeline">
            {universe.timeline.current_era && (
              <>
                <dt>Current era</dt>
                <dd>{universe.timeline.current_era}</dd>
              </>
            )}
            {universe.timeline.history_context && (
              <>
                <dt>History</dt>
                <dd>{universe.timeline.history_context}</dd>
              </>
            )}
            {universe.timeline.social_structure && (
              <>
                <dt>Social structure</dt>
                <dd>{universe.timeline.social_structure}</dd>
              </>
            )}
            {universe.timeline.timeline_notes && (
              <>
                <dt>Notes</dt>
                <dd>{universe.timeline.timeline_notes}</dd>
              </>
            )}
          </dl>
        </section>
      )}
    </div>
  );
}
