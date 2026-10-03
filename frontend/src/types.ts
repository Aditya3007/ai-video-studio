export interface Series {
  id: string;
  name: string;
  description?: string | null;
  genre?: string | null;
  language: string;
  target_audience?: string | null;
  episode_duration_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface SeriesCreate {
  name: string;
  description?: string;
  genre?: string;
  language?: string;
  target_audience?: string;
  episode_duration_seconds?: number;
}

export interface World {
  id: string;
  series_id: string;
  name: string;
  description?: string | null;
  setting?: string | null;
  era?: string | null;
  current_era?: string | null;
  geography?: string | null;
  technology?: string | null;
  rules?: string | null;
  cultural_context?: string | null;
  history_context?: string | null;
  social_structure?: string | null;
  timeline_notes?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface VisualBible {
  id: string;
  series_id: string;
  art_style?: string | null;
  color_palette?: string | null;
  lighting_style?: string | null;
  camera_style?: string | null;
  lens_style?: string | null;
  composition_style?: string | null;
  environment_style?: string | null;
  character_rendering_style?: string | null;
  aspect_ratio?: string | null;
  visual_notes?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface AudioBible {
  id: string;
  series_id: string;
  voice_style?: string | null;
  narration_style?: string | null;
  dialogue_style?: string | null;
  music_style?: string | null;
  sound_effect_style?: string | null;
  ambient_style?: string | null;
  audio_notes?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Character {
  id: string;
  series_id: string;
  name: string;
  description?: string | null;
  personality?: string | null;
  role?: string | null;
  voice_reference?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Location {
  id: string;
  series_id: string;
  name: string;
  description?: string | null;
  location_type?: string | null;
  atmosphere?: string | null;
  visual_characteristics?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface StoryObject {
  id: string;
  series_id: string;
  name: string;
  description?: string | null;
  object_type?: string | null;
  significance?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface UniverseContext {
  series: Series;
  world: World | null;
  visual_bible: VisualBible | null;
  audio_bible: AudioBible | null;
  timeline: {
    current_era?: string | null;
    history_context?: string | null;
    social_structure?: string | null;
    timeline_notes?: string | null;
  } | null;
  characters: Character[];
  locations: Location[];
  objects: StoryObject[];
}

export interface Story {
  id: string;
  series_id: string;
  title: string;
  description?: string | null;
  source_type: 'COMPLETE_STORY' | 'TOPIC';
  source_content: string;
  language: string;
  status: 'DRAFT' | 'READY' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  extra?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface StoryVersion {
  id: string;
  story_id: string;
  version_number: number;
  content: string;
  change_summary?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
}

export interface StoryAnalysis {
  id: string;
  story_id: string;
  story_version_id: string;
  status: string;
  result: Record<string, unknown>;
  warnings: string[];
  created_at: string;
}

export interface Episode {
  id: string;
  series_id: string;
  title: string;
  description?: string | null;
  episode_number: number;
  status: string;
  source_type: string;
  source_text?: string | null;
  story_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Scene {
  id: string;
  episode_id: string;
  scene_number: number;
  title?: string | null;
  description?: string | null;
  time_of_day?: string | null;
  sequence_order: number;
  location_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ShotSpecification {
  id: string;
  shot_id: string;
  intent?: string | null;
  framing?: string | null;
  composition?: string | null;
  camera_notes?: string | null;
  camera_movement?: string | null;
  subject_notes?: string | null;
  visual_direction?: string | null;
  aspect_ratio?: string | null;
  duration_seconds?: number | null;
  character_refs?: string[] | null;
  location_refs?: string[] | null;
  object_refs?: string[] | null;
  output_constraints?: Record<string, unknown> | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Shot {
  id: string;
  scene_id: string;
  shot_number: number;
  description?: string | null;
  action?: string | null;
  camera?: string | null;
  camera_movement?: string | null;
  lighting?: string | null;
  mood?: string | null;
  duration_seconds: number;
  dialogue?: string | null;
  narration?: string | null;
  sequence_order: number;
  specification: ShotSpecification | null;
  created_at: string;
  updated_at: string;
}

export interface StudioShotSummary {
  id: string;
  shot_number: number;
  description?: string | null;
  duration_seconds?: number | null;
  action?: string | null;
  has_specification: boolean;
  asset_count: number;
}

export interface StudioSceneSummary {
  id: string;
  scene_number: number;
  title?: string | null;
  description?: string | null;
  location_id?: string | null;
  shot_count: number;
  shots: StudioShotSummary[];
}

export interface StudioEpisodeProduction {
  series_id: string;
  episode: Episode;
  story: Story | null;
  scenes: StudioSceneSummary[];
  assembly: Record<string, unknown>;
  qa_status?: string | null;
}

export interface StudioShotProduction {
  series_id: string;
  episode_id: string;
  scene_id: string;
  shot: Shot;
  specification: ShotSpecification | null;
  assets: Asset[];
  assembly_item_count: number;
  qa_status?: string | null;
}

export interface Asset {
  id: string;
  series_id: string;
  asset_type: string;
  role: string;
  status: string;
  approval_status: string | null;
  storage_backend: string;
  storage_key: string | null;
  name: string | null;
  description: string | null;
  asset_metadata: Record<string, unknown> | null;
  shot_id: string | null;
  character_ids: string[];
  location_ids: string[];
  object_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface ImageGenerationJob {
  id: string;
  series_id: string;
  shot_id: string | null;
  request_payload: Record<string, unknown> | null;
  status: string;
  approval_status: string | null;
  attempts: number;
  max_attempts: number;
  result_asset_ids: string[] | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImageToVideoResponse {
  videos: Record<string, unknown>[];
  provider: string;
  model: string;
  request_id: string | null;
  metadata: Record<string, unknown> | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface CostBreakdown {
  value: string;
  total_cost: string;
  generation_count: number;
}

export interface EpisodeSummary {
  episode_id: string;
  title: string;
  actual_spend: string;
  generation_count: number;
  budget_amount: string | null;
  budget_currency: string | null;
  budget_status: string;
  remaining_budget: string | null;
  utilization: string;
}

export interface SeriesEconomics {
  series_id: string;
  total_actual_cost: string;
  generation_count: number;
  episode_count: number;
  average_cost_per_generation: string;
  cost_by_generation_type: CostBreakdown[];
  cost_by_provider: CostBreakdown[];
  cost_by_model: CostBreakdown[];
  total_configured_budget: string;
  total_actual_spend: string;
  total_reserved: string;
  total_remaining_budget: string;
  budget_utilization: string;
  budget_currency: string | null;
  episode_summaries: EpisodeSummary[];
}

export interface EpisodeEconomics {
  series_id: string;
  episode_id: string;
  title: string;
  actual_spend: string;
  generation_count: number;
  average_cost_per_generation: string;
  cost_by_generation_type: CostBreakdown[];
  cost_by_provider: CostBreakdown[];
  cost_by_model: CostBreakdown[];
  generation_count_by_type: Record<string, number>;
  budget_amount: string | null;
  budget_currency: string | null;
  budget_status: string;
  active_reservation: string;
  remaining_budget: string | null;
  available_budget: string | null;
  utilization: string;
  usage_limits: Record<string, unknown> | null;
}
