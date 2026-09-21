import { useEffect, useState } from 'react';
import { api } from './api';

export function useApi<T>(path: string, revision = 0) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    setData(undefined); setError(''); setLoading(true);
    api<T>(path, { signal: abort.signal }).then(value => {
      if (!abort.signal.aborted) setData(value);
    }).catch(reason => {
      if (!abort.signal.aborted) setError(reason instanceof Error ? reason.message : 'The application request failed.');
    }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [path, revision, attempt]);
  return { data, error, loading, reload: () => setAttempt(value => value + 1) };
}
