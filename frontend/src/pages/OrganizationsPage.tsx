import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Building2, Pencil, Trash2 } from 'lucide-react';
import { api } from '../lib/api';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { useToast } from '../hooks/useToast';

interface Organization {
  id: string;
  name: string;
  slug: string;
  kind: 'school' | 'company' | 'personal';
  default_mode: string | null;
  default_capabilities: string | null;
  system_prompt_override: string | null;
  created_at: string;
  updated_at: string;
}

type OrganizationKind = Organization['kind'];

const emptyOrganizationForm = {
  name: '',
  slug: '',
  kind: 'company' as OrganizationKind,
  default_mode: '',
  default_capabilities: '',
  system_prompt_override: '',
};

export function OrganizationsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingOrg, setEditingOrg] = useState<Organization | null>(null);
  const [formData, setFormData] = useState(emptyOrganizationForm);

  const { data: orgs, isLoading } = useQuery({
    queryKey: ['organizations'],
    queryFn: async () => {
      const res = await api.get('/api/organizations');
      return res.data as Organization[];
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      const res = await api.post('/api/organizations', data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
      setIsModalOpen(false);
      toast({ title: 'Organization created', variant: 'success' });
    },
    onError: (err: any) => {
      toast({ title: 'Error', description: err.response?.data?.detail || 'Failed to create organization', variant: 'error' });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: typeof formData }) => {
      const res = await api.put(`/api/organizations/${id}`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
      setIsModalOpen(false);
      setEditingOrg(null);
      toast({ title: 'Organization updated', variant: 'success' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/organizations/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
      toast({ title: 'Organization deleted', variant: 'success' });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingOrg) {
      updateMutation.mutate({ id: editingOrg.id, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  const openEdit = (org: Organization) => {
    setEditingOrg(org);
    setFormData({
      name: org.name,
      slug: org.slug,
      kind: org.kind,
      default_mode: org.default_mode || '',
      default_capabilities: org.default_capabilities || '',
      system_prompt_override: org.system_prompt_override || '',
    });
    setIsModalOpen(true);
  };

  const openCreate = () => {
    setEditingOrg(null);
    setFormData(emptyOrganizationForm);
    setIsModalOpen(true);
  };

  if (isLoading) return <div className="p-8">Loading...</div>;

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Organizations</h1>
        <Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" /> Create Organization</Button>
      </div>

      <div className="grid gap-4">
        {orgs?.map((org) => (
          <Card key={org.id} className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Building2 className="h-5 w-5 text-blue-500" />
                <div>
                  <div className="font-semibold">{org.name}</div>
                  <div className="text-sm text-gray-500">{org.slug} · {org.kind}</div>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => openEdit(org)}><Pencil className="h-4 w-4" /></Button>
                <Button variant="ghost" size="sm" onClick={() => deleteMutation.mutate(org.id)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
              </div>
            </div>
            {org.default_mode && <div className="mt-2 text-sm text-gray-600">Default mode: {org.default_mode}</div>}
            {org.default_capabilities && <div className="text-sm text-gray-600">Capabilities: {org.default_capabilities}</div>}
          </Card>
        ))}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingOrg ? 'Edit Organization' : 'Create Organization'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
          <Input label="Slug" value={formData.slug} onChange={(e) => setFormData({ ...formData, slug: e.target.value })} required />
          <Select label="Kind" value={formData.kind} onChange={(e) => setFormData({ ...formData, kind: e.target.value as OrganizationKind })} options={[{ value: 'school', label: 'School' }, { value: 'company', label: 'Company' }, { value: 'personal', label: 'Personal' }]} />
          <Input label="Default Mode" value={formData.default_mode} onChange={(e) => setFormData({ ...formData, default_mode: e.target.value })} placeholder="headmaster_local, headmaster_remote, headmaster_plus_thin" />
          <Input label="Default Capabilities" value={formData.default_capabilities} onChange={(e) => setFormData({ ...formData, default_capabilities: e.target.value })} placeholder="comma-separated list" />
          <Input label="System Prompt Override" value={formData.system_prompt_override} onChange={(e) => setFormData({ ...formData, system_prompt_override: e.target.value })} placeholder="Optional system prompt" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>Cancel</Button>
            <Button type="submit" isLoading={createMutation.isPending || updateMutation.isPending}>{editingOrg ? 'Update' : 'Create'}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
