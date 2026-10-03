import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { EntityManager } from './EntityManager.tsx';

afterEach(cleanup);

interface TestEntity {
  id: string;
  name: string;
  note: string;
}

describe('EntityManager', () => {
  it('renders entities and calls onDelete after confirmation', () => {
    vi.stubGlobal('confirm', () => true);
    const onDelete = vi.fn().mockResolvedValue(undefined);
    const entities: TestEntity[] = [
      { id: '1', name: 'One', note: 'a' },
      { id: '2', name: 'Two', note: 'b' },
    ];

    render(
      <EntityManager<TestEntity>
        title="Items"
        entities={entities}
        emptyMessage="No items."
        defaultValues={{ name: '', note: '' }}
        renderForm={(values, onChange) => (
          <>
            <label>
              Name
              <input
                value={values.name || ''}
                onChange={(e) => onChange({ name: e.target.value })}
              />
            </label>
            <label>
              Note
              <input
                value={values.note || ''}
                onChange={(e) => onChange({ note: e.target.value })}
              />
            </label>
          </>
        )}
        onSave={vi.fn()}
        onDelete={onDelete}
      />
    );

    fireEvent.click(screen.getAllByText('Delete')[0]);
    expect(onDelete).toHaveBeenCalledWith('1');
  });

  it('calls onSave with form values when creating', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <EntityManager<TestEntity>
        title="Items"
        entities={[]}
        emptyMessage="No items."
        defaultValues={{ name: '', note: '' }}
        renderForm={(values, onChange) => (
          <>
            <label>
              Name
              <input
                value={values.name || ''}
                onChange={(e) => onChange({ name: e.target.value })}
              />
            </label>
          </>
        )}
        onSave={onSave}
        onDelete={vi.fn()}
      />
    );

    const inputs = screen.getAllByLabelText('Name');
    fireEvent.change(inputs[inputs.length - 1], { target: { value: 'New' } });
    fireEvent.click(screen.getByText('Create'));

    await screen.findByText('Create');
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ name: 'New' }));
  });
});
