import type {
  Asset,
  AudioBible,
  Character,
  Episode,
  EpisodeEconomics,
  ImageGenerationJob,
  ImageToVideoResponse,
  Location,
  PaginatedResponse,
  Series,
  SeriesCreate,
  SeriesEconomics,
  Story,
  StoryAnalysis,
  StoryObject,
  StoryVersion,
  StudioEpisodeProduction,
  StudioShotProduction,
  UniverseContext,
  VisualBible,
  World,
} from '../types.ts';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const data = (await response.json()) as { message?: string; detail?: string };
      message = data.message || data.detail || message;
    } catch {
      // ignore parse error
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function listSeries(): Promise<Series[]> {
  const response = await request<PaginatedResponse<Series>>('/series?limit=100');
  return response.items;
}

export async function createSeries(body: SeriesCreate): Promise<Series> {
  return request<Series>('/series', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateSeries(id: string, body: Partial<SeriesCreate>): Promise<Series> {
  return request<Series>(`/series/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteSeries(id: string): Promise<void> {
  return request<void>(`/series/${id}`, { method: 'DELETE' });
}

export async function getUniverse(seriesId: string): Promise<UniverseContext> {
  return request<UniverseContext>(`/series/${seriesId}/universe`);
}

export async function getWorld(seriesId: string): Promise<World> {
  return request<World>(`/series/${seriesId}/world`);
}

export async function createWorld(seriesId: string, body: Partial<World>): Promise<World> {
  return request<World>(`/series/${seriesId}/world`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateWorld(worldId: string, body: Partial<World>): Promise<World> {
  return request<World>(`/worlds/${worldId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteWorld(worldId: string): Promise<void> {
  return request<void>(`/worlds/${worldId}`, { method: 'DELETE' });
}

export async function getVisualBible(seriesId: string): Promise<VisualBible> {
  return request<VisualBible>(`/series/${seriesId}/visual-bible`);
}

export async function createVisualBible(
  seriesId: string,
  body: Partial<VisualBible>
): Promise<VisualBible> {
  return request<VisualBible>(`/series/${seriesId}/visual-bible`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateVisualBible(
  seriesId: string,
  body: Partial<VisualBible>
): Promise<VisualBible> {
  return request<VisualBible>(`/series/${seriesId}/visual-bible`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function getAudioBible(seriesId: string): Promise<AudioBible> {
  return request<AudioBible>(`/series/${seriesId}/audio-bible`);
}

export async function createAudioBible(
  seriesId: string,
  body: Partial<AudioBible>
): Promise<AudioBible> {
  return request<AudioBible>(`/series/${seriesId}/audio-bible`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateAudioBible(
  seriesId: string,
  body: Partial<AudioBible>
): Promise<AudioBible> {
  return request<AudioBible>(`/series/${seriesId}/audio-bible`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function listCharacters(seriesId: string): Promise<Character[]> {
  const response = await request<PaginatedResponse<Character>>(
    `/series/${seriesId}/characters?limit=100`
  );
  return response.items;
}

export async function createCharacter(
  seriesId: string,
  body: Partial<Character>
): Promise<Character> {
  return request<Character>(`/series/${seriesId}/characters`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateCharacter(
  seriesId: string,
  characterId: string,
  body: Partial<Character>
): Promise<Character> {
  return request<Character>(`/series/${seriesId}/characters/${characterId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteCharacter(seriesId: string, characterId: string): Promise<void> {
  return request<void>(`/series/${seriesId}/characters/${characterId}`, {
    method: 'DELETE',
  });
}

export async function listLocations(seriesId: string): Promise<Location[]> {
  const response = await request<PaginatedResponse<Location>>(
    `/series/${seriesId}/locations?limit=100`
  );
  return response.items;
}

export async function createLocation(seriesId: string, body: Partial<Location>): Promise<Location> {
  return request<Location>(`/series/${seriesId}/locations`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateLocation(
  seriesId: string,
  locationId: string,
  body: Partial<Location>
): Promise<Location> {
  return request<Location>(`/series/${seriesId}/locations/${locationId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteLocation(seriesId: string, locationId: string): Promise<void> {
  return request<void>(`/series/${seriesId}/locations/${locationId}`, {
    method: 'DELETE',
  });
}

export async function listObjects(seriesId: string): Promise<StoryObject[]> {
  const response = await request<PaginatedResponse<StoryObject>>(
    `/series/${seriesId}/objects?limit=100`
  );
  return response.items;
}

export async function createObject(
  seriesId: string,
  body: Partial<StoryObject>
): Promise<StoryObject> {
  return request<StoryObject>(`/series/${seriesId}/objects`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateObject(
  seriesId: string,
  objectId: string,
  body: Partial<StoryObject>
): Promise<StoryObject> {
  return request<StoryObject>(`/series/${seriesId}/objects/${objectId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteObject(seriesId: string, objectId: string): Promise<void> {
  return request<void>(`/series/${seriesId}/objects/${objectId}`, {
    method: 'DELETE',
  });
}

export async function listStories(seriesId: string): Promise<Story[]> {
  const response = await request<PaginatedResponse<Story>>(`/series/${seriesId}/stories?limit=100`);
  return response.items;
}

export async function getStory(seriesId: string, storyId: string): Promise<Story> {
  return request<Story>(`/series/${seriesId}/stories/${storyId}`);
}

export async function listStoryVersions(
  seriesId: string,
  storyId: string
): Promise<StoryVersion[]> {
  const response = await request<PaginatedResponse<StoryVersion>>(
    `/series/${seriesId}/stories/${storyId}/versions?limit=100`
  );
  return response.items;
}

export async function listStoryAnalyses(
  seriesId: string,
  storyId: string
): Promise<StoryAnalysis[]> {
  const response = await request<PaginatedResponse<StoryAnalysis>>(
    `/series/${seriesId}/stories/${storyId}/analysis?limit=100`
  );
  return response.items;
}

export async function listEpisodes(seriesId: string): Promise<Episode[]> {
  const response = await request<PaginatedResponse<Episode>>(
    `/series/${seriesId}/episodes?limit=100`
  );
  return response.items;
}

export async function getEpisodeStudio(
  seriesId: string,
  episodeId: string
): Promise<StudioEpisodeProduction> {
  return request<StudioEpisodeProduction>(`/series/${seriesId}/episodes/${episodeId}/studio`);
}

export async function getShotStudio(
  seriesId: string,
  shotId: string
): Promise<StudioShotProduction> {
  return request<StudioShotProduction>(`/series/${seriesId}/shots/${shotId}/studio`);
}

export async function createImageGenerationJob(
  seriesId: string,
  shotId: string,
  body: { prompt_override?: string; reference_asset_ids?: string[] }
): Promise<ImageGenerationJob> {
  return request<ImageGenerationJob>(`/series/${seriesId}/shots/${shotId}/image-generation-jobs`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function approveImageGenerationJob(
  seriesId: string,
  jobId: string
): Promise<ImageGenerationJob> {
  return request<ImageGenerationJob>(`/series/${seriesId}/image-generation-jobs/${jobId}/approve`, {
    method: 'POST',
  });
}

export async function rejectImageGenerationJob(
  seriesId: string,
  jobId: string
): Promise<ImageGenerationJob> {
  return request<ImageGenerationJob>(`/series/${seriesId}/image-generation-jobs/${jobId}/reject`, {
    method: 'POST',
  });
}

export async function retryImageGenerationJob(
  seriesId: string,
  jobId: string
): Promise<ImageGenerationJob> {
  return request<ImageGenerationJob>(`/series/${seriesId}/image-generation-jobs/${jobId}/retry`, {
    method: 'POST',
  });
}

export async function listAssets(seriesId: string): Promise<Asset[]> {
  const response = await request<PaginatedResponse<Asset>>(`/series/${seriesId}/assets?limit=100`);
  return response.items;
}

export async function updateAsset(
  seriesId: string,
  assetId: string,
  body: Partial<Omit<Asset, 'id' | 'series_id' | 'created_at' | 'updated_at'>>
): Promise<Asset> {
  return request<Asset>(`/series/${seriesId}/assets/${assetId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function generateImageToVideo(
  seriesId: string,
  shotId: string,
  body: {
    storyboard_asset_id: string;
    prompt_override?: string;
    duration_seconds?: number;
    aspect_ratio?: string;
    motion_description?: string;
    reference_asset_ids?: string[];
  }
): Promise<ImageToVideoResponse> {
  return request<ImageToVideoResponse>(`/series/${seriesId}/shots/${shotId}/image-to-video`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getSeriesEconomics(seriesId: string): Promise<SeriesEconomics> {
  return request<SeriesEconomics>(`/series/${seriesId}/economics`);
}

export async function getEpisodeEconomics(
  seriesId: string,
  episodeId: string
): Promise<EpisodeEconomics> {
  return request<EpisodeEconomics>(`/series/${seriesId}/episodes/${episodeId}/economics`);
}
