import { useEffect, useState } from 'react';
import { fetchPublications } from '../lib/publications';

interface Props {
  type?: 'all' | 'journal' | 'conference';
  suffix?: string;
}

export default function PublicationCount({ type = 'all', suffix = '' }: Props) {
  const [count, setCount] = useState<number | null>(null);
  useEffect(() => {
    fetchPublications().then(data => {
      setCount(
        type === 'all'
          ? data.total
          : data.typeCounts?.[type] ?? data.papers.filter(paper => paper.type === type).length,
      );
    }).catch(() => setCount(null));
  }, [type]);
  return <>{count === null ? '—' : `${count}${suffix}`}</>;
}
