import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ReferenceWorkspace } from './ReferenceWorkspace';
import { CapacityWorkspace } from './CapacityWorkspace';
import { NAVIGATION_SECTIONS } from './reference/domain/data';
import type { Session } from './contracts';

afterEach(() => {cleanup(); vi.unstubAllGlobals();});
const session = { authenticated:true, synthetic:true, role:'analyst', csrfToken:'synthetic-csrf' } as Session;
const catalog = {definitions:[], presets:[{name:'MVP',profileId:'mvp',availability:'single',historyMode:'changed',platform:'unselected',parameters:{}}]};
const result = {inputHash:'fixture-hash',scenario:catalog.presets[0],totals:{cpu:2,memoryGiB:8},storage:{},allocations:[],equations:[],warnings:[],blockers:[],assumptions:[],
  cost:{isAvailable:false,totalMonthly:null,currency:'USD',basis:'Unknown prices'},deployable:false,performanceVerified:false};

describe('one application modules', () => {
  it('preserves all reference topics and guided explanation without another login', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}',{status:503})));
    window.location.hash = '#reference';
    render(<ReferenceWorkspace />);
    const nav = screen.getByRole('navigation', {name:'Reference topics'});
    expect(nav.querySelectorAll('button')).toHaveLength(12);
    for (const topic of NAVIGATION_SECTIONS) {
      fireEvent.click(screen.getByRole('button', {name:topic.shortLabel,exact:true}));
      expect(screen.getByRole('button',{name:topic.shortLabel,exact:true})).toHaveAttribute('aria-pressed','true');
    }
    fireEvent.click(screen.getByRole('button',{name:'Guided explanation'}));
    expect(screen.getByRole('button',{name:'Next explanation'})).toBeEnabled();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });
  it('calculates through the shared C# API and invalidates stale estimates after edits', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(catalog))).mockResolvedValueOnce(new Response(JSON.stringify(result)));
    vi.stubGlobal('fetch', fetcher);
    render(<CapacityWorkspace session={session} />);
    fireEvent.click(await screen.findByRole('button',{name:'Use mvp tier'}));
    fireEvent.click(screen.getByRole('button',{name:'Calculate scenario'}));
    expect(await screen.findByRole('region',{name:'Capacity calculation result'})).toBeInTheDocument();
    expect(fetcher.mock.calls[1][0]).toBe('/api/capacity/calculate');
    expect(new Headers(fetcher.mock.calls[1][1].headers).get('X-PQC-CSRF')).toBe('synthetic-csrf');
    fireEvent.change(screen.getByLabelText('Scenario name'), {target:{value:'Changed input'}});
    expect(screen.queryByRole('region',{name:'Capacity calculation result'})).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Inputs changed');
  });
  it('shows API failure without claiming a plan or infrastructure change', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(catalog))).mockResolvedValueOnce(new Response('{}',{status:403})));
    render(<CapacityWorkspace session={session} />);
    fireEvent.click(await screen.findByRole('button',{name:'Calculate scenario'}));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('no plan was saved or infrastructure changed'));
  });
});
