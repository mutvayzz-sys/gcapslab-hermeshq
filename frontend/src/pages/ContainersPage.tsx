import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Container, Play, Square, Trash2, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { useToast } from '../hooks/useToast';

interface ContainerItem {
  id: string;
  user_id: string;
  organization_id: string | null;
  name: string;
  status: 'pending' | 'creating' | 'running' | 'stopped' | 'error' | 'destroyed';
  docker_container_id: string | null;
  image: string;
  health_check_url: string | null;
  last_healthy_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export function ContainersPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: containers, isLoading } = useQuery({
    queryKey: ['containers'],
    queryFn: async () => {
      const res = await api.get('/api/containers');
      return res.data as ContainerItem[];
    },
  });

  const startMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/api/containers/${id}/start`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
      toast({ title: 'Container started', variant: 'success' });
    },
  });

  const stopMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/api/containers/${id}/stop`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
      toast({ title: 'Container stopped', variant: 'success' });
    },
  });

  const destroyMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/containers/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
      toast({ title: 'Container destroyed', variant: 'success' });
    },
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'green';
      case 'stopped': return 'yellow';
      case 'error': return 'red';
      case 'pending': return 'gray';
      case 'creating': return 'blue';
      default: return 'gray';
    }
  };

  if (isLoading) return <div className="p-8">Loading...</div>;

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Containers</h1>
        <Button onClick={() => queryClient.invalidateQueries({ queryKey: ['containers'] })}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      <div className="grid gap-4">
        {containers?.map((container) => (
          <Card key={container.id} className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Container className="h-5 w-5 text-blue-500" />
                <div>
                  <div className="font-semibold">{container.name}</div>
                  <div className="text-sm text-gray-500">
                    {container.image} · {container.docker_container_id || 'No Docker ID'}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant={getStatusColor(container.status)}>{container.status}</Badge>
                <div className="flex gap-1">
                  {container.status === 'stopped' && (
                    <Button variant="ghost" size="sm" onClick={() => startMutation.mutate(container.id)}>
                      <Play className="h-4 w-4 text-green-500" />
                    </Button>
                  )}
                  {container.status === 'running' && (
                    <Button variant="ghost" size="sm" onClick={() => stopMutation.mutate(container.id)}>
                      <Square className="h-4 w-4 text-yellow-500" />
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => destroyMutation.mutate(container.id)}>
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              </div>
            </div>
            {container.health_check_url && (
              <div className="mt-2 text-sm text-gray-600">Health: {container.health_check_url}</div>
            )}
            {container.error_message && (
              <div className="mt-2 text-sm text-red-500">Error: {container.error_message}</div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
