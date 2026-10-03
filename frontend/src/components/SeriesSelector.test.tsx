import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { SeriesSelector } from './SeriesSelector.tsx';

afterEach(cleanup);

import type { Series } from '../types.ts';

const seriesList: Series[] = [
  {
    id: 's1',
    name: 'Alpha',
    language: 'en',
    episode_duration_seconds: 60,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 's2',
    name: 'Beta',
    language: 'en',
    episode_duration_seconds: 60,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

describe('SeriesSelector', () => {
  it('renders the series list and allows selection', () => {
    const onSelect = vi.fn();
    render(
      <SeriesSelector
        seriesList={[...seriesList]}
        selectedId={null}
        loading={false}
        error={null}
        onSelect={onSelect}
        onCreate={vi.fn()}
      />
    );

    expect(screen.queryByText('Alpha')).not.toBeNull();
    expect(screen.queryByText('Beta')).not.toBeNull();

    fireEvent.click(screen.getByText('Beta'));
    expect(onSelect).toHaveBeenCalledWith('s2');
  });

  it('shows an empty state when there are no series', () => {
    render(
      <SeriesSelector
        seriesList={[]}
        selectedId={null}
        loading={false}
        error={null}
        onSelect={vi.fn()}
        onCreate={vi.fn()}
      />
    );

    expect(screen.queryByText('No series yet.')).not.toBeNull();
  });

  it('creates a new series when the form is submitted', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <SeriesSelector
        seriesList={[]}
        selectedId={null}
        loading={false}
        error={null}
        onSelect={vi.fn()}
        onCreate={onCreate}
      />
    );

    fireEvent.click(screen.getByText('+ New Series'));
    const input = screen.getByPlaceholderText('New series name');
    fireEvent.change(input, { target: { value: 'Gamma' } });
    fireEvent.click(screen.getByText('Create'));

    await screen.findByText('+ New Series');
    expect(onCreate).toHaveBeenCalledWith({ name: 'Gamma' });
  });
});
