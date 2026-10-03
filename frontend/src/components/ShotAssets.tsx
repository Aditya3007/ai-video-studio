/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from 'react';
import {
  approveImageGenerationJob,
  createImageGenerationJob,
  generateImageToVideo,
  rejectImageGenerationJob,
  retryImageGenerationJob,
} from '../api/client.ts';
import type {
  Asset,
  ImageGenerationJob,
  ImageToVideoResponse,
  ShotSpecification,
} from '../types.ts';
import { ErrorMessage, Loading } from './Status.tsx';
import './ShotAssets.css';

interface ShotAssetsProps {
  seriesId: string;
  shotId: string;
  assets: Asset[];
  specification: ShotSpecification | null;
  onRefresh: () => Promise<void>;
}

export function ShotAssets({
  seriesId,
  shotId,
  assets,
  specification,
  onRefresh,
}: ShotAssetsProps) {
  const [job, setJob] = useState<ImageGenerationJob | null>(null);
  const [jobLoading, setJobLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');
  const [videoResult, setVideoResult] = useState<ImageToVideoResponse | null>(null);
  const [videoLoading, setVideoLoading] = useState(false);
  const [videoPrompt, setVideoPrompt] = useState('');
  const [videoMotion, setVideoMotion] = useState('');
  const [selectedStoryboardId, setSelectedStoryboardId] = useState<string | null>(null);

  const eligibleForVideo = useMemo(
    () =>
      assets.filter(
        (a) =>
          a.approval_status === 'APPROVED' &&
          (a.asset_type === 'IMAGE' || a.asset_type === 'STORYBOARD' || a.asset_type === 'KEYFRAME')
      ),
    [assets]
  );

  useEffect(() => {
    setSelectedStoryboardId(eligibleForVideo[0]?.id ?? null);
  }, [eligibleForVideo]);

  useEffect(() => {
    setJob(null);
    setVideoResult(null);
    setError(null);
  }, [shotId]);

  const handleGenerate = async () => {
    setJobLoading(true);
    setError(null);
    try {
      const body: { prompt_override?: string; reference_asset_ids?: string[] } = {
        reference_asset_ids: [],
      };
      if (prompt.trim()) body.prompt_override = prompt.trim();
      const created = await createImageGenerationJob(seriesId, shotId, body);
      setJob(created);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Image generation failed');
    } finally {
      setJobLoading(false);
    }
  };

  const mutateJob = async (
    action: (seriesId: string, jobId: string) => Promise<ImageGenerationJob>
  ) => {
    if (!job) return;
    setJobLoading(true);
    setError(null);
    try {
      const updated = await action(seriesId, job.id);
      setJob(updated);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Job update failed');
    } finally {
      setJobLoading(false);
    }
  };

  const handleVideo = async () => {
    if (!selectedStoryboardId) return;
    setVideoLoading(true);
    setError(null);
    try {
      const body: {
        storyboard_asset_id: string;
        prompt_override?: string;
        duration_seconds?: number;
        aspect_ratio?: string;
        motion_description?: string;
        reference_asset_ids?: string[];
      } = {
        storyboard_asset_id: selectedStoryboardId,
        reference_asset_ids: [],
      };
      if (videoPrompt.trim()) body.prompt_override = videoPrompt.trim();
      if (videoMotion.trim()) body.motion_description = videoMotion.trim();
      if (specification?.duration_seconds) body.duration_seconds = specification.duration_seconds;
      if (specification?.aspect_ratio) body.aspect_ratio = specification.aspect_ratio;
      const result = await generateImageToVideo(seriesId, shotId, body);
      setVideoResult(result);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Video generation failed');
    } finally {
      setVideoLoading(false);
    }
  };

  return (
    <section className="shot-assets" aria-labelledby="assets-heading">
      <h3 id="assets-heading">Assets & Generation</h3>
      {error && <ErrorMessage message={error} />}
      {jobLoading && <Loading />}

      <section className="asset-list" aria-label="Existing assets">
        {assets.length === 0 ? (
          <p className="empty">No assets for this shot.</p>
        ) : (
          assets.map((asset) => (
            <article key={asset.id} className="asset-card">
              <h4>{asset.name || `${asset.asset_type} asset`}</h4>
              <p className="meta">
                {asset.asset_type} · {asset.role} · {asset.status} ·{' '}
                {asset.approval_status || 'no approval'}
              </p>
              {asset.description && <p>{asset.description}</p>}
              {(asset.asset_type === 'IMAGE' ||
                asset.asset_type === 'STORYBOARD' ||
                asset.asset_type === 'KEYFRAME') && (
                <div className="preview-unavailable">Image preview unavailable</div>
              )}
              {asset.asset_metadata && (
                <pre className="asset-metadata">
                  {JSON.stringify(asset.asset_metadata, null, 2)}
                </pre>
              )}
            </article>
          ))
        )}
      </section>

      <section className="generation-panel" aria-label="Image generation">
        <h4>Generate image</h4>
        <label htmlFor="prompt-override">Prompt override (optional)</label>
        <input
          id="prompt-override"
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Optional prompt override"
        />
        <button type="button" onClick={handleGenerate} disabled={jobLoading}>
          {jobLoading ? 'Generating...' : 'Generate image'}
        </button>

        {job && (
          <div className="job-card">
            <p className="meta">
              Job {job.id} · {job.status}
              {job.approval_status && ` · ${job.approval_status}`}
            </p>
            {job.error_message && <p className="error">{job.error_message}</p>}
            {job.attempts > 0 && (
              <p className="meta">
                Attempt {job.attempts} of {job.max_attempts}
              </p>
            )}
            {job.status === 'SUCCEEDED' && job.approval_status === 'PENDING' && (
              <div className="job-actions">
                <button
                  type="button"
                  onClick={() => mutateJob(approveImageGenerationJob)}
                  disabled={jobLoading}
                >
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() => mutateJob(rejectImageGenerationJob)}
                  disabled={jobLoading}
                >
                  Reject
                </button>
              </div>
            )}
            {job.status === 'FAILED' && (
              <button
                type="button"
                onClick={() => mutateJob(retryImageGenerationJob)}
                disabled={jobLoading}
              >
                Retry
              </button>
            )}
          </div>
        )}
      </section>

      {eligibleForVideo.length > 0 && (
        <section className="video-panel" aria-label="Image to video handoff">
          <h4>Generate video</h4>
          <label htmlFor="storyboard-select">Storyboard asset</label>
          <select
            id="storyboard-select"
            value={selectedStoryboardId ?? ''}
            onChange={(e) => setSelectedStoryboardId(e.target.value)}
          >
            {eligibleForVideo.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name || asset.id}
              </option>
            ))}
          </select>
          <label htmlFor="video-prompt">Prompt override (optional)</label>
          <input
            id="video-prompt"
            type="text"
            value={videoPrompt}
            onChange={(e) => setVideoPrompt(e.target.value)}
            placeholder="Optional prompt override"
          />
          <label htmlFor="video-motion">Motion description (optional)</label>
          <input
            id="video-motion"
            type="text"
            value={videoMotion}
            onChange={(e) => setVideoMotion(e.target.value)}
            placeholder="Optional motion description"
          />
          <button type="button" onClick={handleVideo} disabled={videoLoading}>
            {videoLoading ? 'Generating video...' : 'Generate video'}
          </button>
          {videoResult && (
            <pre className="video-result">{JSON.stringify(videoResult, null, 2)}</pre>
          )}
        </section>
      )}
    </section>
  );
}
