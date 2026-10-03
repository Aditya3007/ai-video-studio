import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import {
  getEpisodeStudio,
  getShotStudio,
  listEpisodes,
  listStories,
  listStoryAnalyses,
  listStoryVersions,
} from '../api/client.ts';
import { StoryWorkspace } from './StoryWorkspace.tsx';

vi.mock('../api/client.ts', () => ({
  listStories: vi.fn(),
  listEpisodes: vi.fn(),
  listStoryVersions: vi.fn(),
  listStoryAnalyses: vi.fn(),
  getEpisodeStudio: vi.fn(),
  getShotStudio: vi.fn(),
}));

const baseStory = {
  id: 'story-1',
  series_id: 'series-1',
  title: 'Story One',
  description: 'A test story',
  source_type: 'COMPLETE_STORY' as const,
  source_content: 'Once upon a time...',
  language: 'en',
  status: 'DRAFT' as const,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const baseEpisode = {
  id: 'episode-1',
  series_id: 'series-1',
  title: 'Episode One',
  description: 'First episode',
  episode_number: 1,
  status: 'DRAFT',
  source_type: 'TOPIC',
  source_text: 'Episode source text',
  story_id: 'story-1',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const baseShot = {
  id: 'shot-1',
  scene_id: 'scene-1',
  shot_number: 1,
  description: 'Hero enters',
  action: 'Walk in',
  camera: 'Wide',
  camera_movement: 'Static',
  lighting: 'Day',
  mood: 'Hopeful',
  duration_seconds: 5,
  dialogue: null,
  narration: null,
  sequence_order: 0,
  specification: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

beforeEach(() => {
  vi.mocked(listStories).mockResolvedValue([baseStory]);
  vi.mocked(listEpisodes).mockResolvedValue([baseEpisode]);
  vi.mocked(listStoryVersions).mockResolvedValue([
    {
      id: 'version-1',
      story_id: 'story-1',
      version_number: 1,
      content: 'The story content',
      change_summary: 'Initial',
      created_at: '2024-01-01T00:00:00Z',
    },
  ]);
  vi.mocked(listStoryAnalyses).mockResolvedValue([
    {
      id: 'analysis-1',
      story_id: 'story-1',
      story_version_id: 'version-1',
      status: 'completed',
      result: { narrative: { acts: [] } },
      warnings: [],
      created_at: '2024-01-01T00:00:00Z',
    },
  ]);
  vi.mocked(getEpisodeStudio).mockResolvedValue({
    series_id: 'series-1',
    episode: baseEpisode,
    story: baseStory,
    scenes: [
      {
        id: 'scene-1',
        scene_number: 1,
        title: 'Scene One',
        description: 'The first scene',
        shot_count: 1,
        shots: [
          {
            id: 'shot-1',
            shot_number: 1,
            description: 'Hero enters',
            duration_seconds: 5,
            action: 'Walk in',
            has_specification: true,
            asset_count: 0,
          },
        ],
      },
    ],
    assembly: {},
    qa_status: null,
  });
  vi.mocked(getShotStudio).mockResolvedValue({
    series_id: 'series-1',
    episode_id: 'episode-1',
    scene_id: 'scene-1',
    shot: baseShot,
    specification: {
      id: 'spec-1',
      shot_id: 'shot-1',
      intent: 'Establish hero',
      framing: 'Wide',
      aspect_ratio: '16:9',
      duration_seconds: 5,
      character_refs: [],
      location_refs: [],
      object_refs: [],
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    assets: [],
    assembly_item_count: 0,
    qa_status: null,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('StoryWorkspace', () => {
  it('renders stories and loads details on selection', async () => {
    render(<StoryWorkspace seriesId="series-1" />);

    await screen.findByText('Story One');
    fireEvent.click(screen.getByText('Story One'));

    await waitFor(() => {
      expect(vi.mocked(listStoryVersions)).toHaveBeenCalledWith('series-1', 'story-1');
      expect(vi.mocked(listStoryAnalyses)).toHaveBeenCalledWith('series-1', 'story-1');
    });
    await screen.findByText(/Version 1/);
  });

  it('navigates episode → scene → shot and loads shot specification', async () => {
    render(<StoryWorkspace seriesId="series-1" />);

    await screen.findByText('Story One');
    fireEvent.click(screen.getByText('Story One'));
    await screen.findByText('Episodes for Story One');
    fireEvent.click(screen.getByText('E1: Episode One'));

    await waitFor(() => {
      expect(vi.mocked(getEpisodeStudio)).toHaveBeenCalledWith('series-1', 'episode-1');
    });
    await screen.findByText('S1: Scene One');
    fireEvent.click(screen.getByText('S1: Scene One'));
    await screen.findByText('#1 Hero enters');
    fireEvent.click(screen.getByText('#1 Hero enters'));

    await waitFor(() => {
      expect(vi.mocked(getShotStudio)).toHaveBeenCalledWith('series-1', 'shot-1');
    });
    await screen.findByText('Shot #1 — Hero enters');
    await screen.findByText('16:9');
  });

  it('clears selections when the series changes', async () => {
    const { rerender } = render(<StoryWorkspace seriesId="series-1" />);
    await screen.findByText('Story One');
    fireEvent.click(screen.getByText('Story One'));
    await screen.findByText('Episodes for Story One');

    vi.mocked(listStories).mockResolvedValue([{ ...baseStory, id: 'story-2', title: 'Story Two' }]);
    vi.mocked(listEpisodes).mockResolvedValue([]);

    rerender(<StoryWorkspace seriesId="series-2" />);
    await waitFor(() => {
      expect(vi.mocked(listStories)).toHaveBeenCalledWith('series-2');
    });
    expect(screen.queryByText('Episodes for Story One')).toBeNull();
  });
});
