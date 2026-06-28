import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Container, Play, Square, Trash2, RefreshCw, Plus } from 'lucide-react';
import { api } from '../lib/api';
import { useUsers } from '../api/users';
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
  const [showProvision, setShowProvision] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [containerName, setContainerName] = useState('');

  const { data: containers, isLoading } = useQuery({
    queryKey: ['containers'],
    queryFn: async () => {
      const res = await api.get('/api/containers');
      return res.data as ContainerItem[];
    },
  });

  const { data: users } = useUsers(showProvision);

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

  const provisionMutation = useMutation({
    mutationFn: async ({ user_id, name }: { user_id: string; name?: string }) => {
      const res = await api.post('/api/containers/provision', { user_id, name: name || undefined });
      return res.data as ContainerItem;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
      toast({ title: 'Container provisioned', variant: 'success' });
      setShowProvision(false);
      setSelectedUserId('');
      setContainerName('');
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? 'Provisioning failed';
      toast({ title: detail, variant: 'error' });
    },
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'green';
      case 'stopped':
        return 'yellow';
      case 'error':
        return 'red';
      case 'pending':
        return 'gray';
      case 'creating':
        return 'blue';
      default:
        return 'gray';
    }
  };

  if (isLoading) return <div className='p-8'>Loading...</div>;

  return (
    <div className='p-8'>
      <div className='mb-6 flex items-center justify-between'>
        <h1 className='text-2xl font-bold'>Containers</h1>
        <div className='flex gap-2'>
          <Button variant='outline' onClick={() => queryClient.invalidateQueries({ queryKey: ['containers'] })}>
            <RefreshCw className='mr-2 h-4 w-4' /> Refresh
          </Button>
          <Button onClick={() => setShowProvision(true)}>
            <Plus className='mr-2 h-4 w-4' /> Provision User
          </Button>
        </div>
      </div>

      {showProvision && (
        <Card className='mb-6 p-6'>
          <h2 className='mb-4 text-lg font-semibold'>Provision Hermes Container</h2>
          <div className='flex flex-col gap-4'>
            <div>
              <label className='mb-1 block text-sm font-medium text-gray-700'>User</label>
              <select
                className='w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
              >
                <option value=''>Select a user…</option>
                {users?.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.username} ({u.role})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className='mb-1 block text-sm font-medium text-gray-700'>
                Container name <span className='text-gray-400'>(optional — auto-generated if blank)</span>
              </label>
              <input
                type='text'
                className='w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'
                placeholder='hermes-alice'
                value={containerName}
                onChange={(e) => setContainerName(e.target.value)}
              />
            </div>
            <div className='text-xs text-gray-500'>
              Image: <code>hermes:latest</code> · Port 8080 mapped to an ephemeral host port
            </div>
            <div className='flex gap-2'>
              <Button
                onClick={() => provisionMutation.mutate({ user_id: selectedUserId, name: containerName || undefined })}
                disabled={!selectedUserId || provisionMutation.isPending}
              >
                {provisionMutation.isPending ? 'Provisioning…' : 'Provision'}
              </Button>
              <Button
                variant='outline'
                onClick={() => {
                  setShowProvision(false);
                  setSelectedUserId('');
                  setContainerName('');
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        </Card>
      )}

      <div className='grid gap-4'>
        {containers?.length === 0 && (
          <div className='py-12 text-center text-gray-500'>
            No containers yet. Click "Provision User" to create one.
          </div>
        )}
        {containers?.map((container) => (
          <Card key={container.id} className='p-4'>
            <div className='flex items-center justify-between'>
              <div className='flex items-center gap-3'>
                <Container className='h-5 w-5 text-blue-500' />
                <div>
                  <div className='font-semibold'>{container.name}</div>
                  <div className='text-sm text-gray-500'>
                    {container.image} · {container.docker_container_id || 'No Docker ID'}
                  </div>
                </div>
              </div>
              <div className='flex items-center gap-3'>
                <Badge variant={getStatusColor(container.status)}>{container.status}</Badge>
                <div className='flex gap-1'>
                  {container.status === 'stopped' && (
                    <Button variant='ghost' size='sm' onClick={() => startMutation.mutate(container.id)}>
                      <Play className='h-4 w-4 text-green-500' />
                    </Button>
                  )}
                  {container.status === 'running' && (
                    <Button variant='ghost' size='sm' onClick={() => stopMutation.mutate(container.id)}>
                      <Square className='h-4 w-4 text-yellow-500' />
                    </Button>
                  )}
                  <Button variant='ghost' size='sm' onClick={() => destroyMutation.mutate(container.id)}>
                    <Trash2 className='h-4 w-4 text-red-500' />
                  </Button>
                </div>
              </div>
            </div>
            {container.health_check_url && (
              <div className='mt-2 text-sm text-gray-600'>Health: {container.health_check_url}</div>
            )}
            {container.error_message && (
              <div className='mt-2 text-sm text-red-500'>Error: {container.error_message}</div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
