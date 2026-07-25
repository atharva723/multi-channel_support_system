import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { KbApi, type KbDocument, type UploadFile } from '../api/client';

export const kbKeys = {
  all: ['kb'] as const,
  list: ['kb', 'documents'] as const,
};

/** List the account's knowledge-base documents. Polls while any are processing. */
export function useKnowledgeBase() {
  return useQuery({
    queryKey: kbKeys.list,
    queryFn: () => KbApi.list(),
    // Auto-refresh while a document is still embedding so the progress bar and
    // status update in near real time (embedding is fast; poll briskly).
    refetchInterval: (query) => {
      const docs = query.state.data as KbDocument[] | undefined;
      return docs?.some((d) => d.status === 'processing') ? 1200 : false;
    },
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: UploadFile) => KbApi.upload(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: kbKeys.list }),
  });
}

export function useReplaceDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, file }: { id: number; file: UploadFile }) =>
      KbApi.replace(id, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: kbKeys.list }),
  });
}

export function useAddWebsite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => KbApi.addWebsite(url),
    onSuccess: () => qc.invalidateQueries({ queryKey: kbKeys.list }),
  });
}

export function useResyncSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => KbApi.resync(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: kbKeys.list }),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => KbApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: kbKeys.list }),
  });
}
