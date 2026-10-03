import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import {
  approveImageGenerationJob,
  createImageGenerationJob,
  generateImageToVideo,
  rejectImageGenerationJob,
  retryImageGenerationJob,
} from '../api/client.ts';
import type { ShotSpecification } from '../types.ts';
import { ShotAssets } from './ShotAssets.tsx';

vi.mock('../api/client.ts', () => ({
  createImageGenerationJob: vi.fn(),
  approveImageGenerationJob: vi.fn(),
  rejectImageGenerationJob: vi.fn(),
  retryImageGenerationJob: vi.fn(),
  generateImageToVideo: vi.fn(),
}));

const baseAsset = {
  id: 'asset-1',
  series_id: 'series-1',
  asset_type: 'IMAGE',
  role: 'GENERATED',
  status: 'AVAILABLE',
  approval_status: 'PENDING',
  storage_backend: 'default',
  storage_key: 'shots/1/asset.png',
  name: 'Generated frame',
  description: 'A test frame',
  asset_metadata: { width: 1024, height: 1024 },
  shot_id: 'shot-1',
  character_ids: [],
  location_ids: [],
  object_ids: [],
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const approvedStoryboard = {
  ...baseAsset,
  id: 'asset-2',
  name: 'Approved storyboard',
  asset_type: 'STORYBOARD',
  role: 'STORYBOARD',
  approval_status: 'APPROVED',
};

const baseJob = {
  id: 'job-1',
  series_id: 'series-1',
  shot_id: 'shot-1',
  request_payload: {},
  status: 'SUCCEEDED',
  approval_status: 'PENDING',
  attempts: 1,
  max_attempts: 3,
  result_asset_ids: ['asset-1'],
  error_message: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const failedJob = {
  ...baseJob,
  status: 'FAILED',
  error_message: 'Provider error',
};

beforeEach(() => {
  vi.mocked(createImageGenerationJob).mockResolvedValue(baseJob);
  vi.mocked(approveImageGenerationJob).mockResolvedValue({
    ...baseJob,
    approval_status: 'APPROVED',
  });
  vi.mocked(rejectImageGenerationJob).mockResolvedValue({
    ...baseJob,
    approval_status: 'REJECTED',
  });
  vi.mocked(retryImageGenerationJob).mockResolvedValue({ ...failedJob, status: 'SUCCEEDED' });
  vi.mocked(generateImageToVideo).mockResolvedValue({
    videos: [{ asset_id: 'video-1' }],
    provider: 'fake',
    model: 'test',
    request_id: 'req-1',
    metadata: {},
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ShotAssets', () => {
  it('renders asset metadata and empty state', () => {
    render(
      <ShotAssets
        seriesId="series-1"
        shotId="shot-1"
        assets={[baseAsset]}
        specification={null}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />
    );

    expect(screen.getByText('Generated frame')).toBeDefined();
    expect(screen.getByText('IMAGE · GENERATED · AVAILABLE · PENDING')).toBeDefined();
    expect(screen.getByText('Image preview unavailable')).toBeDefined();
  });

  it('shows empty state when no assets', () => {
    render(
      <ShotAssets
        seriesId="series-1"
        shotId="shot-1"
        assets={[]}
        specification={null}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />
    );
    expect(screen.getByText('No assets for this shot.')).toBeDefined();
  });

  it('triggers image generation and approval', async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(
      <ShotAssets
        seriesId="series-1"
        shotId="shot-1"
        assets={[baseAsset]}
        specification={null}
        onRefresh={onRefresh}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Generate image/ }));
    await waitFor(() => {
      expect(vi.mocked(createImageGenerationJob)).toHaveBeenCalledWith('series-1', 'shot-1', {
        reference_asset_ids: [],
      });
    });

    await screen.findByText(/SUCCEEDED/);
    fireEvent.click(screen.getByText('Approve'));
    await waitFor(() => {
      expect(vi.mocked(approveImageGenerationJob)).toHaveBeenCalledWith('series-1', 'job-1');
    });
    expect(onRefresh).toHaveBeenCalled();
  });

  it('shows failed job and retry', async () => {
    vi.mocked(createImageGenerationJob).mockResolvedValue(failedJob);
    render(
      <ShotAssets
        seriesId="series-1"
        shotId="shot-1"
        assets={[baseAsset]}
        specification={null}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Generate image/ }));
    await screen.findByText('Provider error');
    fireEvent.click(screen.getByText('Retry'));
    await waitFor(() => {
      expect(vi.mocked(retryImageGenerationJob)).toHaveBeenCalledWith('series-1', 'job-1');
    });
  });

  it('triggers image-to-video handoff for approved storyboard', async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(
      <ShotAssets
        seriesId="series-1"
        shotId="shot-1"
        assets={[approvedStoryboard]}
        specification={
          {
            id: 'spec-1',
            shot_id: 'shot-1',
            duration_seconds: 5,
            aspect_ratio: '16:9',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          } as ShotSpecification
        }
        onRefresh={onRefresh}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Generate video/ }));
    await waitFor(() => {
      expect(vi.mocked(generateImageToVideo)).toHaveBeenCalledWith(
        'series-1',
        'shot-1',
        expect.objectContaining({
          storyboard_asset_id: 'asset-2',
          duration_seconds: 5,
          aspect_ratio: '16:9',
          reference_asset_ids: [],
        })
      );
    });
    await screen.findByText(/"asset_id": "video-1"/);
  });
});
