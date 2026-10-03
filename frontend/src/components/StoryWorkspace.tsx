/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getEpisodeStudio,
  getShotStudio,
  listEpisodes,
  listStories,
  listStoryAnalyses,
  listStoryVersions,
} from '../api/client.ts';
import type {
  Episode,
  Story,
  StoryAnalysis,
  StoryVersion,
  StudioEpisodeProduction,
  StudioSceneSummary,
  StudioShotProduction,
} from '../types.ts';
import { ShotAssets } from './ShotAssets.tsx';
import { ErrorMessage, Loading } from './Status.tsx';
import './StoryWorkspace.css';

interface StoryWorkspaceProps {
  seriesId: string;
}

export function StoryWorkspace({ seriesId }: StoryWorkspaceProps) {
  const [stories, setStories] = useState<Story[]>([]);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedStoryId, setSelectedStoryId] = useState<string | null>(null);
  const [storyVersions, setStoryVersions] = useState<StoryVersion[]>([]);
  const [storyAnalyses, setStoryAnalyses] = useState<StoryAnalysis[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(null);
  const [episodeProduction, setEpisodeProduction] = useState<StudioEpisodeProduction | null>(null);
  const [productionLoading, setProductionLoading] = useState(false);

  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [selectedShotId, setSelectedShotId] = useState<string | null>(null);
  const [shotProduction, setShotProduction] = useState<StudioShotProduction | null>(null);
  const [shotLoading, setShotLoading] = useState(false);

  const loadStoriesAndEpisodes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [storyItems, episodeItems] = await Promise.all([
        listStories(seriesId),
        listEpisodes(seriesId),
      ]);
      setStories(storyItems);
      setEpisodes(episodeItems);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stories');
    } finally {
      setLoading(false);
    }
  }, [seriesId]);

  useEffect(() => {
    loadStoriesAndEpisodes();
  }, [loadStoriesAndEpisodes]);

  useEffect(() => {
    setStoryVersions([]);
    setStoryAnalyses([]);
    if (!selectedStoryId) return;
    let cancelled = false;
    setDetailLoading(true);
    setError(null);
    Promise.all([
      listStoryVersions(seriesId, selectedStoryId),
      listStoryAnalyses(seriesId, selectedStoryId),
    ])
      .then(([versions, analyses]) => {
        if (!cancelled) {
          setStoryVersions(versions);
          setStoryAnalyses(analyses);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load story details');
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [seriesId, selectedStoryId]);

  useEffect(() => {
    setSelectedSceneId(null);
    setSelectedShotId(null);
    setShotProduction(null);
    if (!selectedEpisodeId) {
      setEpisodeProduction(null);
      return;
    }
    let cancelled = false;
    setProductionLoading(true);
    setError(null);
    getEpisodeStudio(seriesId, selectedEpisodeId)
      .then((prod) => {
        if (!cancelled) setEpisodeProduction(prod);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load episode production');
        }
      })
      .finally(() => {
        if (!cancelled) setProductionLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [seriesId, selectedEpisodeId]);

  useEffect(() => {
    setSelectedShotId(null);
    setShotProduction(null);
  }, [selectedSceneId]);

  useEffect(() => {
    if (!selectedShotId) {
      setShotProduction(null);
      return;
    }
    let cancelled = false;
    setShotLoading(true);
    setError(null);
    getShotStudio(seriesId, selectedShotId)
      .then((prod) => {
        if (!cancelled) setShotProduction(prod);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load shot');
        }
      })
      .finally(() => {
        if (!cancelled) setShotLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [seriesId, selectedShotId]);

  const selectedStory = useMemo(
    () => stories.find((s) => s.id === selectedStoryId),
    [stories, selectedStoryId]
  );
  const selectedEpisode = useMemo(
    () => episodes.find((e) => e.id === selectedEpisodeId),
    [episodes, selectedEpisodeId]
  );
  const episodesForStory = useMemo(
    () => episodes.filter((e) => e.story_id === selectedStoryId),
    [episodes, selectedStoryId]
  );
  const selectedScene = useMemo(
    () => episodeProduction?.scenes.find((s) => s.id === selectedSceneId),
    [episodeProduction, selectedSceneId]
  );

  const refreshShot = useCallback(async () => {
    if (!selectedShotId) return;
    setShotLoading(true);
    setError(null);
    try {
      const prod = await getShotStudio(seriesId, selectedShotId);
      setShotProduction(prod);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reload shot');
    } finally {
      setShotLoading(false);
    }
  }, [seriesId, selectedShotId]);

  const handleSelectStory = (id: string) => {
    setSelectedStoryId(id);
    setSelectedEpisodeId(null);
    setSelectedSceneId(null);
    setSelectedShotId(null);
  };

  const handleSelectEpisode = (id: string) => {
    setSelectedEpisodeId(id);
    setSelectedSceneId(null);
    setSelectedShotId(null);
  };

  if (loading && stories.length === 0) return <Loading />;

  return (
    <div className="story-workspace">
      {error && <ErrorMessage message={error} />}
      <nav className="story-nav" aria-label="Story and episode navigation">
        <h3>Stories</h3>
        {stories.length === 0 ? (
          <p className="empty">No stories for this series.</p>
        ) : (
          <ul className="story-list">
            {stories.map((story) => (
              <li key={story.id}>
                <button
                  type="button"
                  className={story.id === selectedStoryId ? 'selected' : ''}
                  onClick={() => handleSelectStory(story.id)}
                >
                  {story.title}
                </button>
              </li>
            ))}
          </ul>
        )}
        {selectedStory && (
          <section className="episode-list-section">
            <h4>Episodes for {selectedStory.title}</h4>
            {episodesForStory.length === 0 ? (
              <p className="empty">No episodes for this story.</p>
            ) : (
              <ul className="episode-list">
                {episodesForStory.map((episode) => (
                  <li key={episode.id}>
                    <button
                      type="button"
                      className={episode.id === selectedEpisodeId ? 'selected' : ''}
                      onClick={() => handleSelectEpisode(episode.id)}
                    >
                      E{episode.episode_number}: {episode.title}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </nav>
      <nav className="scene-nav" aria-label="Scene and shot navigation">
        {episodeProduction && (
          <>
            <h3>Scenes</h3>
            {episodeProduction.scenes.length === 0 ? (
              <p className="empty">No scenes planned.</p>
            ) : (
              <ul className="scene-list">
                {episodeProduction.scenes.map((scene) => (
                  <li key={scene.id}>
                    <button
                      type="button"
                      className={scene.id === selectedSceneId ? 'selected' : ''}
                      onClick={() => setSelectedSceneId(scene.id)}
                    >
                      S{scene.scene_number}: {scene.title || 'Untitled'}
                    </button>
                    {scene.id === selectedSceneId && (
                      <ul className="shot-list">
                        {scene.shots.length === 0 ? (
                          <li className="empty">No shots.</li>
                        ) : (
                          scene.shots.map((shot) => (
                            <li key={shot.id}>
                              <button
                                type="button"
                                className={shot.id === selectedShotId ? 'selected' : ''}
                                onClick={() => setSelectedShotId(shot.id)}
                              >
                                #{shot.shot_number} {shot.description || ''}
                              </button>
                            </li>
                          ))
                        )}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
        {!episodeProduction && !productionLoading && selectedEpisodeId && (
          <p className="empty">Select an episode to see scenes.</p>
        )}
        {productionLoading && <Loading />}
      </nav>
      <section className="story-detail" aria-live="polite">
        {(detailLoading || productionLoading || shotLoading) && <Loading />}
        {selectedShotId && shotProduction && (
          <>
            <ShotDetail production={shotProduction} />
            <ShotAssets
              seriesId={shotProduction.series_id}
              shotId={shotProduction.shot.id}
              assets={shotProduction.assets}
              specification={shotProduction.specification}
              onRefresh={refreshShot}
            />
          </>
        )}
        {!selectedShotId && selectedScene && <SceneDetail scene={selectedScene} />}
        {!selectedShotId && !selectedScene && selectedEpisode && episodeProduction && (
          <EpisodeDetail episode={selectedEpisode} production={episodeProduction} />
        )}
        {!selectedShotId && !selectedScene && !selectedEpisode && selectedStory && (
          <StoryDetail story={selectedStory} versions={storyVersions} analyses={storyAnalyses} />
        )}
        {!selectedStory && !loading && (
          <p className="empty">Select a story to inspect its production workspace.</p>
        )}
      </section>
    </div>
  );
}

function StoryDetail({
  story,
  versions,
  analyses,
}: {
  story: Story;
  versions: StoryVersion[];
  analyses: StoryAnalysis[];
}) {
  return (
    <>
      <h2>{story.title}</h2>
      <p className="meta">
        {story.status} · {story.source_type} · {story.language}
      </p>
      {story.description && <p>{story.description}</p>}
      <section className="source-section">
        <h3>Source</h3>
        <pre className="source-content">{story.source_content}</pre>
      </section>
      <section>
        <h3>Versions</h3>
        {versions.length === 0 ? (
          <p className="empty">No versions recorded.</p>
        ) : (
          <ul>
            {versions.map((v) => (
              <li key={v.id}>
                Version {v.version_number}
                {v.change_summary && ` — ${v.change_summary}`}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3>Analysis</h3>
        {analyses.length === 0 ? (
          <p className="empty">No analyses recorded.</p>
        ) : (
          <ul>
            {analyses.map((a) => (
              <li key={a.id}>
                {a.status} · {a.warnings.length} warning(s)
                <pre className="json">{JSON.stringify(a.result, null, 2)}</pre>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

function EpisodeDetail({
  episode,
  production,
}: {
  episode: Episode;
  production: StudioEpisodeProduction;
}) {
  return (
    <>
      <h2>
        E{episode.episode_number}: {episode.title}
      </h2>
      <p className="meta">
        {episode.status} · {production.scenes.length} scene(s)
      </p>
      {episode.description && <p>{episode.description}</p>}
      {episode.source_text && (
        <section className="source-section">
          <h3>Source text</h3>
          <pre className="source-content">{episode.source_text}</pre>
        </section>
      )}
    </>
  );
}

function SceneDetail({ scene }: { scene: StudioSceneSummary }) {
  return (
    <>
      <h2>
        S{scene.scene_number}: {scene.title || 'Untitled'}
      </h2>
      {scene.description && <p>{scene.description}</p>}
      <p className="meta">{scene.shot_count} shot(s)</p>
    </>
  );
}

function ShotDetail({ production }: { production: StudioShotProduction }) {
  const { shot, specification } = production;
  return (
    <>
      <h2>
        Shot #{shot.shot_number} {shot.description && `— ${shot.description}`}
      </h2>
      <dl className="shot-fields">
        {shot.action && (
          <>
            <dt>Action</dt>
            <dd>{shot.action}</dd>
          </>
        )}
        {shot.camera && (
          <>
            <dt>Camera</dt>
            <dd>{shot.camera}</dd>
          </>
        )}
        {shot.camera_movement && (
          <>
            <dt>Camera movement</dt>
            <dd>{shot.camera_movement}</dd>
          </>
        )}
        {shot.lighting && (
          <>
            <dt>Lighting</dt>
            <dd>{shot.lighting}</dd>
          </>
        )}
        {shot.mood && (
          <>
            <dt>Mood</dt>
            <dd>{shot.mood}</dd>
          </>
        )}
        <dt>Duration</dt>
        <dd>{shot.duration_seconds}s</dd>
        {shot.dialogue && (
          <>
            <dt>Dialogue</dt>
            <dd>{shot.dialogue}</dd>
          </>
        )}
        {shot.narration && (
          <>
            <dt>Narration</dt>
            <dd>{shot.narration}</dd>
          </>
        )}
      </dl>
      {specification ? (
        <section className="spec-section">
          <h3>Specification</h3>
          <dl className="shot-fields">
            {specification.intent && (
              <>
                <dt>Intent</dt>
                <dd>{specification.intent}</dd>
              </>
            )}
            {specification.framing && (
              <>
                <dt>Framing</dt>
                <dd>{specification.framing}</dd>
              </>
            )}
            {specification.composition && (
              <>
                <dt>Composition</dt>
                <dd>{specification.composition}</dd>
              </>
            )}
            {specification.aspect_ratio && (
              <>
                <dt>Aspect ratio</dt>
                <dd>{specification.aspect_ratio}</dd>
              </>
            )}
            {specification.duration_seconds && (
              <>
                <dt>Specified duration</dt>
                <dd>{specification.duration_seconds}s</dd>
              </>
            )}
            {specification.character_refs && specification.character_refs.length > 0 && (
              <>
                <dt>Character refs</dt>
                <dd>{specification.character_refs.join(', ')}</dd>
              </>
            )}
            {specification.location_refs && specification.location_refs.length > 0 && (
              <>
                <dt>Location refs</dt>
                <dd>{specification.location_refs.join(', ')}</dd>
              </>
            )}
            {specification.object_refs && specification.object_refs.length > 0 && (
              <>
                <dt>Object refs</dt>
                <dd>{specification.object_refs.join(', ')}</dd>
              </>
            )}
          </dl>
        </section>
      ) : (
        <p className="empty">No specification recorded.</p>
      )}
    </>
  );
}
