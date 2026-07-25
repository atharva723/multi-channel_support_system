import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { AuthApi, type Connection } from '../api/client';

export const connectionKeys = {
  all: ['connections'] as const,
  guilds: ['connections', 'discord', 'guilds'] as const,
};

export function useConnections() {
  return useQuery({
    queryKey: connectionKeys.all,
    queryFn: () => AuthApi.connections(),
  });
}

export function useDeleteConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => AuthApi.deleteConnection(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: connectionKeys.all }),
  });
}

export function useDiscordGuilds(enabled: boolean) {
  return useQuery({
    queryKey: connectionKeys.guilds,
    queryFn: () => AuthApi.discordGuilds(),
    enabled,
  });
}

export function useLinkGuild() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (guildId: string) => AuthApi.linkGuild(guildId),
    onSuccess: (updated: Connection) => {
      qc.invalidateQueries({ queryKey: connectionKeys.all });
      qc.invalidateQueries({ queryKey: connectionKeys.guilds });
    },
  });
}
