'use client';

import { useState } from 'react';
import {
  Server,
  Cpu,
  Settings2,
  Plus,
  Pencil,
  Trash2,
  Check,
  X,
  ExternalLink,
  RefreshCw,
  Terminal,
} from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import * as Select from '@radix-ui/react-select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useQueryClient } from '@tanstack/react-query';
import {
  useProviders,
  useCreateProvider,
  useUpdateProvider,
  useDeleteProvider,
  useTestProvider,
  useTestModel,
  useProviderModels,
  useModels,
  useCreateModel,
  useUpdateModel,
  useDeleteModel,
  useAgentModelConfig,
  useSetAgentModelConfig,
  useDeleteAgentModelConfig,
  useAvailableAgents,
} from '@/lib/hooks/useProviders';
import type { LLMProvider, LLMModel } from '@/types';

// ─── Provider Dialog ──────────────────────────────────────────────────────────

function ProviderFormDialog({
  open,
  onOpenChange,
  provider,
  onSave,
  loading,
  error,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  provider?: LLMProvider | null;
  onSave: (data: { name: string; slug: string; description?: string | null; api_base_url?: string | null; api_key?: string | null }) => void;
  loading: boolean;
  error: string | null;
}) {
  const testMutation = useTestProvider();

  const [name, setName] = useState(provider?.name ?? '');
  const [slug, setSlug] = useState(provider?.slug ?? '');
  const [description, setDescription] = useState(provider?.description ?? '');
  const [apiBaseUrl, setApiBaseUrl] = useState(provider?.api_base_url ?? '');
  const [apiKey, setApiKey] = useState(provider?.api_key ?? '');
  const [slugTouched, setSlugTouched] = useState(!!provider?.slug);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; latency_ms?: number } | null>(null);

  const toSlug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const handleNameChange = (val: string) => {
    setName(val);
    if (!slugTouched) setSlug(toSlug(val));
  };

  const handleSlugChange = (val: string) => {
    setSlugTouched(true);
    setSlug(val);
  };

  const handleTest = async () => {
    if (!apiBaseUrl.trim()) return;
    setTestResult(null);
    try {
      const result = await testMutation.mutateAsync({
        api_base_url: apiBaseUrl.trim(),
        api_key: apiKey || null,
      });
      setTestResult(result);
    } catch {
      setTestResult({ success: false, message: 'Connection test failed' });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !slug.trim()) return;
    onSave({
      name: name.trim(),
      slug: slug.trim(),
      description: description || null,
      api_base_url: apiBaseUrl || null,
      api_key: apiKey || null,
    });
  };

  const isNew = !provider;
  const testPassed = testResult?.success === true;
  const canSubmit = name.trim() && slug.trim() && (!isNew || testPassed);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl bg-card p-6 shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95">
          <Dialog.Title className="text-lg font-semibold tracking-tight">
            {provider ? 'Edit Provider' : 'Add Provider'}
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted-foreground">
            {provider ? 'Update the LLM provider configuration.' : 'Register a new LLM provider.'}
          </Dialog.Description>

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="OpenAI"
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Slug</label>
              <Input
                value={slug}
                onChange={(e) => handleSlugChange(e.target.value)}
                placeholder="openai"
                required
              />
              <p className="text-xs text-muted-foreground">Unique identifier used in API calls.</p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="OpenAI API - GPT-4o, GPT-4-turbo, and more"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">API Base URL</label>
              <Input
                value={apiBaseUrl}
                onChange={(e) => setApiBaseUrl(e.target.value)}
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">API Key</label>
              <Input
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                type="password"
              />
              <p className="text-xs text-muted-foreground">Stored encrypted in production. Leave blank for keyless providers (Ollama).</p>
            </div>

            {/* Test Connection */}
            <div className="pt-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleTest}
                disabled={testMutation.isPending || !apiBaseUrl.trim()}
                className="gap-1.5"
              >
                {testMutation.isPending ? (
                  <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                ) : (
                  <span className="h-3 w-3 rounded-full border border-current" />
                )}
                {testMutation.isPending ? 'Testing...' : 'Test Connection'}
              </Button>
              {testResult && (
                <p className={`mt-1.5 text-xs ${testResult.success ? 'text-success' : 'text-destructive'}`}>
                  {testResult.success ? '\u2713 ' : '\u2717 '}
                  {testResult.message}
                  {testResult.latency_ms != null && ` (${testResult.latency_ms}ms)`}
                </p>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              {error && (
                <p className="mr-auto text-xs text-destructive">{error}</p>
              )}
              <Dialog.Close asChild>
                <Button type="button" variant="outline">Cancel</Button>
              </Dialog.Close>
              <Button type="submit" disabled={loading || !canSubmit} title={isNew && !testPassed ? 'Test connection first' : ''}>
                {loading ? 'Saving...' : provider ? 'Update' : 'Create'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ─── Model Dialog ─────────────────────────────────────────────────────────────

function ModelFormDialog({
  open,
  onOpenChange,
  model,
  providerId,
  providers,
  onSave,
  loading,
  error,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  model?: LLMModel | null;
  providerId?: string | null;
  providers: LLMProvider[];
  onSave: (data: {
    name: string;
    slug: string;
    description?: string | null;
    max_tokens: number;
    default_temperature?: number;
    providerId: string;
  }) => void;
  loading: boolean;
  error: string | null;
}) {
  const testMutation = useTestModel();

  const [name, setName] = useState(model?.name ?? '');
  const [slug, setSlug] = useState(model?.slug ?? '');
  const [description, setDescription] = useState(model?.description ?? '');
  const [maxTokens, setMaxTokens] = useState(String(model?.max_tokens ?? 4096));
  const [temperature, setTemperature] = useState(String(model?.default_temperature ?? 0.1));
  const [selectedProviderId, setSelectedProviderId] = useState(providerId ?? providers[0]?.id ?? '');
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; latency_ms?: number; available_models?: string[] } | null>(null);

  const handleTest = async () => {
    if (!slug.trim() || !selectedProviderId) return;
    setTestResult(null);
    try {
      const result = await testMutation.mutateAsync({
        provider_id: selectedProviderId,
        model_slug: slug.trim(),
      });
      setTestResult(result);
    } catch {
      setTestResult({ success: false, message: 'Model test failed' });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      name,
      slug,
      description: description || null,
      max_tokens: parseInt(maxTokens, 10) || 4096,
      default_temperature: parseFloat(temperature) || 0.1,
      providerId: selectedProviderId,
    });
  };

  const isNew = !model;
  const testPassed = testResult?.success === true;
  const canSubmit = name.trim() && slug.trim() && (!isNew || testPassed);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl bg-card p-6 shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95">
          <Dialog.Title className="text-lg font-semibold tracking-tight">
            {model ? 'Edit Model' : 'Add Model'}
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted-foreground">
            {model ? 'Update the model configuration.' : 'Register a new model under a provider.'}
          </Dialog.Description>

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Provider</label>
              <select
                value={selectedProviderId}
                onChange={(e) => setSelectedProviderId(e.target.value)}
                className="flex h-9 w-full rounded-lg border border-input/60 bg-background px-3 py-2 text-sm ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                required
              >
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} ({p.slug})</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Model Name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="GPT-4o" required />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Slug</label>
              <Input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="gpt-4o" required />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Latest OpenAI model" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Max Tokens</label>
                <Input type="number" value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Default Temperature</label>
                <Input type="number" step="0.1" min="0" max="2" value={temperature} onChange={(e) => setTemperature(e.target.value)} />
              </div>
            </div>

            {/* Test Model */}
            <div className="pt-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleTest}
                disabled={testMutation.isPending || !slug.trim() || !selectedProviderId}
                className="gap-1.5"
              >
                {testMutation.isPending ? (
                  <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                ) : (
                  <span className="h-3 w-3 rounded-full border border-current" />
                )}
                {testMutation.isPending ? 'Testing...' : 'Test Model'}
              </Button>
              {testResult && (
                <div className="mt-1.5 space-y-1">
                  <p className={`text-xs ${testResult.success ? 'text-success' : 'text-destructive'}`}>
                    {testResult.success ? '\u2713 ' : '\u2717 '}
                    {testResult.message}
                    {testResult.latency_ms != null && ` (${testResult.latency_ms}ms)`}
                  </p>
                  {testResult.available_models && testResult.available_models.length > 0 && (
                    <details className="text-xs text-muted-foreground">
                      <summary className="cursor-pointer hover:text-foreground transition-colors">
                        Available models ({testResult.available_models.length})
                      </summary>
                      <div className="mt-1 max-h-32 overflow-y-auto rounded border border-border/40 bg-muted/30 p-2 font-mono text-[11px] leading-relaxed">
                        {testResult.available_models.map((m) => (
                          <div key={m} className={m === slug.trim() ? 'text-success font-medium' : ''}>{m}</div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              {error && (
                <p className="mr-auto text-xs text-destructive">{error}</p>
              )}
              <Dialog.Close asChild>
                <Button type="button" variant="outline">Cancel</Button>
              </Dialog.Close>
              <Button type="submit" disabled={loading || !canSubmit} title={isNew && !testPassed ? 'Test the model slug first' : ''}>
                {loading ? 'Saving...' : model ? 'Update' : 'Create'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ─── Agent Config Dialog ──────────────────────────────────────────────────────

function AgentConfigDialog({
  open,
  onOpenChange,
  agentName,
  currentConfig,
  providers,
  onSave,
  onDelete,
  saving,
  error,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  agentName: string;
  currentConfig: { provider_id?: string; model_id?: string; temperature?: number | null; max_tokens?: number | null } | null;
  providers: LLMProvider[];
  onSave: (data: { provider_id: string; model_id: string; temperature?: number | null; max_tokens?: number | null }) => void;
  onDelete: () => void;
  saving: boolean;
  error: string | null;
}) {
  const [selectedProviderId, setSelectedProviderId] = useState(currentConfig?.provider_id ?? providers[0]?.id ?? '');
  const [selectedModelId, setSelectedModelId] = useState(currentConfig?.model_id ?? '');
  const [temperature, setTemperature] = useState(String(currentConfig?.temperature ?? 0.3));
  const [maxTokens, setMaxTokens] = useState(String(currentConfig?.max_tokens ?? 4096));

  const modelsQuery = useProviderModels(selectedProviderId);

  const models = modelsQuery.data?.items ?? [];
  const canDelete = !!currentConfig;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      provider_id: selectedProviderId,
      model_id: selectedModelId,
      temperature: parseFloat(temperature) || null,
      max_tokens: parseInt(maxTokens, 10) || null,
    });
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl bg-card p-6 shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95">
          <Dialog.Title className="text-lg font-semibold tracking-tight">
            Configure Agent: <span className="text-primary">{agentName}</span>
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted-foreground">
            Assign an LLM provider and model to this agent.
          </Dialog.Description>

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Provider</label>
              <select
                value={selectedProviderId}
                onChange={(e) => { setSelectedProviderId(e.target.value); setSelectedModelId(''); }}
                className="flex h-9 w-full rounded-lg border border-input/60 bg-background px-3 py-2 text-sm ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                required
              >
                <option value="">Select provider...</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Model</label>
              <select
                value={selectedModelId}
                onChange={(e) => setSelectedModelId(e.target.value)}
                className="flex h-9 w-full rounded-lg border border-input/60 bg-background px-3 py-2 text-sm ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                required
                disabled={!selectedProviderId}
              >
                <option value="">Select model...</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>{m.name} ({m.slug})</option>
                ))}
              </select>
              {modelsQuery.isLoading && <p className="text-xs text-muted-foreground">Loading models...</p>}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Temperature</label>
                <Input type="number" step="0.1" min="0" max="2" value={temperature} onChange={(e) => setTemperature(e.target.value)} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Max Tokens</label>
                <Input type="number" value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} />
              </div>
            </div>

            {error && (
              <p className="text-xs text-destructive">{error}</p>
            )}

            <div className="flex items-center justify-between pt-2">
              {canDelete && (
                <Button type="button" variant="destructive" size="sm" onClick={onDelete}>
                  <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                  Remove Config
                </Button>
              )}
              <div className="flex items-center gap-3 ml-auto">
                <Dialog.Close asChild>
                  <Button type="button" variant="outline">Cancel</Button>
                </Dialog.Close>
                <Button type="submit" disabled={saving || !selectedModelId}>
                  {saving ? 'Saving...' : 'Save'}
                </Button>
              </div>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="rounded-xl bg-card p-6 shadow-sm border border-border/40">
      <div className="h-5 w-32 shimmer rounded-md" />
      <div className="mt-3 h-4 w-20 shimmer rounded-md" />
      <div className="mt-3 h-4 w-48 shimmer rounded-md" />
      <div className="mt-4 flex gap-2">
        <div className="h-7 w-16 shimmer rounded-md" />
        <div className="h-7 w-16 shimmer rounded-md" />
      </div>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 border-b border-border/40 px-4 py-3">
      <div className="h-4 w-32 shimmer rounded" />
      <div className="h-4 w-20 shimmer rounded" />
      <div className="h-4 w-24 shimmer rounded" />
      <div className="h-4 w-16 shimmer rounded ml-auto" />
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ProvidersPage() {
  const queryClient = useQueryClient();

  // ── Data ──
  const providersQuery = useProviders();
  const modelsQuery = useModels();
  const agentsQuery = useAvailableAgents();
  const providers = providersQuery.data?.items ?? [];
  const models = modelsQuery.data?.items ?? [];

  // ── Mutations ──
  const createProvider = useCreateProvider();
  const updateProvider = useUpdateProvider();
  const deleteProvider = useDeleteProvider();
  const createModel = useCreateModel();
  const updateModel = useUpdateModel();
  const deleteModel = useDeleteModel();
  const setAgentConfig = useSetAgentModelConfig();
  const deleteAgentConfig = useDeleteAgentModelConfig();

  // ── Dialog state ──
  const [providerDialogOpen, setProviderDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null);

  const [modelDialogOpen, setModelDialogOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<LLMModel | null>(null);
  const [modelDialogProviderId, setModelDialogProviderId] = useState<string | null>(null);

  const [agentConfigDialogOpen, setAgentConfigDialogOpen] = useState(false);
  const [configuringAgent, setConfiguringAgent] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const configuringAgentConfigQuery = useAgentModelConfig(configuringAgent);
  const configuringAgentConfig = configuringAgentConfigQuery.data;

  // ── Handlers: Provider ──
  const handleSaveProvider = async (data: { name: string; slug: string; description?: string | null; api_base_url?: string | null; api_key?: string | null }) => {
    setFormError(null);
    try {
      if (editingProvider) {
        await updateProvider.mutateAsync({ id: editingProvider.id, ...data });
      } else {
        await createProvider.mutateAsync(data);
      }
      setProviderDialogOpen(false);
      setEditingProvider(null);
    } catch (err: any) {
      setFormError(err?.body?.error?.message || err?.body?.message || 'Failed to save provider');
    }
  };

  const handleDeleteProvider = async (id: string) => {
    if (!confirm('Delete this provider and all its models?')) return;
    try {
      await deleteProvider.mutateAsync(id);
    } catch { /* */ }
  };

  // ── Handlers: Model ──
  const handleSaveModel = async (data: { name: string; slug: string; description?: string | null; max_tokens: number; default_temperature?: number; providerId: string }) => {
    setFormError(null);
    try {
      if (editingModel) {
        await updateModel.mutateAsync({ id: editingModel.id, ...data });
      } else {
        await createModel.mutateAsync({
          providerId: data.providerId,
          name: data.name,
          slug: data.slug,
          description: data.description,
          max_tokens: data.max_tokens,
          default_temperature: data.default_temperature,
        });
      }
      setModelDialogOpen(false);
      setEditingModel(null);
    } catch (err: any) {
      setFormError(err?.body?.error?.message || err?.body?.message || 'Failed to save model');
    }
  };

  const handleDeleteModel = async (id: string) => {
    if (!confirm('Delete this model?')) return;
    try {
      await deleteModel.mutateAsync(id);
    } catch { /* */ }
  };

  // ── Handlers: Agent Config ──
  const handleSaveAgentConfig = async (data: { provider_id: string; model_id: string; temperature?: number | null; max_tokens?: number | null }) => {
    if (!configuringAgent) return;
    setFormError(null);
    try {
      await setAgentConfig.mutateAsync({ agentName: configuringAgent, ...data });
      setAgentConfigDialogOpen(false);
      setConfiguringAgent(null);
    } catch (err: any) {
      setFormError(err?.body?.error?.message || err?.body?.message || 'Failed to save config');
    }
  };

  const handleDeleteAgentConfig = async () => {
    if (!configuringAgent) return;
    if (!confirm('Remove model configuration for this agent? It will use the default.')) return;
    try {
      await deleteAgentConfig.mutateAsync(configuringAgent);
      setAgentConfigDialogOpen(false);
      setConfiguringAgent(null);
    } catch { /* */ }
  };

  // ── Loading states ──
  const isMutating = createProvider.isPending || updateProvider.isPending || deleteProvider.isPending
    || createModel.isPending || updateModel.isPending || deleteModel.isPending
    || setAgentConfig.isPending;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">LLM Providers</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage LLM providers, models, and per-agent model assignments.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => { queryClient.invalidateQueries(); }}
          disabled={providersQuery.isLoading}
        >
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${providersQuery.isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="providers">
        <TabsList>
          <TabsTrigger value="providers" className="gap-1.5">
            <Server className="h-3.5 w-3.5" />
            Providers
            {providers.length > 0 && (
              <span className="ml-1 rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-medium tabular-nums">
                {providers.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="models" className="gap-1.5">
            <Cpu className="h-3.5 w-3.5" />
            Models
            {models.length > 0 && (
              <span className="ml-1 rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-medium tabular-nums">
                {models.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="agents" className="gap-1.5">
            <Settings2 className="h-3.5 w-3.5" />
            Agent Configs
          </TabsTrigger>
        </TabsList>

        {/* ─────────── Tab: Providers ─────────── */}
        <TabsContent value="providers" className="mt-5">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {providers.length} provider{providers.length !== 1 ? 's' : ''} registered
            </p>
            <Button size="sm" onClick={() => { setEditingProvider(null); setFormError(null); setProviderDialogOpen(true); }}>
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              Add Provider
            </Button>
          </div>

          {providersQuery.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : providers.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-12">
                <Server className="h-8 w-8 text-muted-foreground/30" />
                <p className="text-sm font-medium">No providers configured</p>
                <p className="text-xs text-muted-foreground text-center max-w-sm">
                  Add an LLM provider like OpenAI or Anthropic to get started.
                </p>
                <Button size="sm" variant="outline" onClick={() => { setEditingProvider(null); setFormError(null); setProviderDialogOpen(true); }}>
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  Add Provider
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {providers.map((provider) => (
                <Card key={provider.id} className="relative group">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                          <Server className="h-4 w-4 text-primary" />
                        </div>
                        <div>
                          <CardTitle className="text-base">{provider.name}</CardTitle>
                          <Badge variant="secondary" className="mt-0.5 text-[10px]">
                            {provider.slug}
                          </Badge>
                        </div>
                      </div>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => { setEditingProvider(provider); setProviderDialogOpen(true); }}
                          className="rounded-lg p-1.5 text-muted-foreground/50 hover:bg-accent hover:text-foreground transition-all"
                          title="Edit"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteProvider(provider.id)}
                          className="rounded-lg p-1.5 text-muted-foreground/50 hover:bg-destructive/10 hover:text-destructive transition-all"
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {provider.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{provider.description}</p>
                    )}
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={provider.is_active ? 'success' : 'secondary'} className="text-[10px]">
                        {provider.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                      {provider.api_base_url && (
                        <span className="flex items-center gap-1 text-[10px] text-muted-foreground font-mono truncate max-w-[180px]">
                          <ExternalLink className="h-3 w-3 shrink-0" />
                          {provider.api_base_url}
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* ─────────── Tab: Models ─────────── */}
        <TabsContent value="models" className="mt-5">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {models.length} model{models.length !== 1 ? 's' : ''} registered
            </p>
            <Button size="sm" onClick={() => { setEditingModel(null); setModelDialogProviderId(null); setModelDialogOpen(true); }}>
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              Add Model
            </Button>
          </div>

          {modelsQuery.isLoading ? (
            <Card>
              <CardContent className="p-0">
                {Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)}
              </CardContent>
            </Card>
          ) : models.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-12">
                <Cpu className="h-8 w-8 text-muted-foreground/30" />
                <p className="text-sm font-medium">No models registered</p>
                <p className="text-xs text-muted-foreground text-center max-w-sm">
                  Add models to your providers to make them available for agents.
                </p>
                <Button size="sm" variant="outline" onClick={() => { setEditingModel(null); setModelDialogOpen(true); }}>
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  Add Model
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border/40">
                      <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Model</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Slug</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Provider</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Max Tokens</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground">Streaming</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground">Status</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {models.map((model) => {
                      const provider = providers.find((p) => p.id === model.provider_id);
                      return (
                        <tr key={model.id} className="border-b border-border/20 hover:bg-accent/20 transition-colors">
                          <td className="px-4 py-3 font-medium">{model.name}</td>
                          <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{model.slug}</td>
                          <td className="px-4 py-3 text-muted-foreground">{provider?.name ?? model.provider_id.slice(0, 8)}</td>
                          <td className="px-4 py-3 text-right font-mono text-xs tabular-nums">
                            {model.max_tokens.toLocaleString()}
                          </td>
                          <td className="px-4 py-3 text-center">
                            {model.supports_streaming ? (
                              <Check className="inline h-3.5 w-3.5 text-success" />
                            ) : (
                              <X className="inline h-3.5 w-3.5 text-muted-foreground/40" />
                            )}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <Badge variant={model.is_active ? 'success' : 'secondary'} className="text-[10px]">
                              {model.is_active ? 'Active' : 'Inactive'}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-1">
                              <button
                                onClick={() => {
                                  setEditingModel(model);
                                  setModelDialogProviderId(model.provider_id);
                                  setModelDialogOpen(true);
                                }}
                                className="rounded-lg p-1.5 text-muted-foreground/50 hover:bg-accent hover:text-foreground transition-all"
                                title="Edit"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </button>
                              <button
                                onClick={() => handleDeleteModel(model.id)}
                                className="rounded-lg p-1.5 text-muted-foreground/50 hover:bg-destructive/10 hover:text-destructive transition-all"
                                title="Delete"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ─────────── Tab: Agent Configs ─────────── */}
        <TabsContent value="agents" className="mt-5">
          {agentsQuery.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : !agentsQuery.data || agentsQuery.data.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-12">
                <Terminal className="h-8 w-8 text-muted-foreground/30" />
                <p className="text-sm font-medium">No agents found</p>
                <p className="text-xs text-muted-foreground">Agents are registered at startup from the backend.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {agentsQuery.data.map((agent: { name: string; description?: string }) => (
                <AgentConfigCard
                  key={agent.name}
                  agent={agent}
                  onConfigure={() => { setConfiguringAgent(agent.name); setAgentConfigDialogOpen(true); }}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* ─── Dialogs ─── */}
      <ProviderFormDialog
        open={providerDialogOpen}
        onOpenChange={(v) => { setProviderDialogOpen(v); if (!v) setEditingProvider(null); setFormError(null); }}
        provider={editingProvider}
        onSave={handleSaveProvider}
        loading={isMutating}
        error={formError}
      />

      <ModelFormDialog
        open={modelDialogOpen}
        onOpenChange={(v) => { setModelDialogOpen(v); if (!v) setEditingModel(null); setFormError(null); }}
        model={editingModel}
        providerId={modelDialogProviderId}
        providers={providers}
        onSave={handleSaveModel}
        loading={isMutating}
        error={formError}
      />

      <AgentConfigDialog
        key={configuringAgent ?? 'none'}
        open={agentConfigDialogOpen}
        onOpenChange={(v) => { setAgentConfigDialogOpen(v); if (!v) setConfiguringAgent(null); setFormError(null); }}
        agentName={configuringAgent ?? ''}
        currentConfig={configuringAgentConfig ?? null}
        providers={providers}
        onSave={handleSaveAgentConfig}
        onDelete={handleDeleteAgentConfig}
        saving={isMutating}
        error={formError}
      />
    </div>
  );
}

// ─── Agent Config Card ────────────────────────────────────────────────────────

function AgentConfigCard({
  agent,
  onConfigure,
}: {
  agent: { name: string; description?: string };
  onConfigure: () => void;
}) {
  const configQuery = useAgentModelConfig(agent.name);
  const config = configQuery.data;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
              <Terminal className="h-4 w-4 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">{agent.name}</CardTitle>
              {agent.description && (
                <CardDescription className="text-xs mt-0.5">{agent.description}</CardDescription>
              )}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {configQuery.isLoading ? (
          <div className="h-4 w-32 shimmer rounded" />
        ) : config ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="success" className="text-[10px]">Configured</Badge>
            </div>
            <div className="text-xs text-muted-foreground space-y-0.5">
              <p>Provider: <span className="font-medium text-foreground">{config.provider_name ?? config.provider_id.slice(0, 8)}</span></p>
              <p>Model: <span className="font-medium text-foreground">{config.model_name ?? config.model_slug ?? config.model_id.slice(0, 8)}</span></p>
              {config.max_tokens && <p>Max tokens: <span className="font-medium text-foreground">{config.max_tokens.toLocaleString()}</span></p>}
              {config.temperature != null && <p>Temperature: <span className="font-medium text-foreground">{config.temperature}</span></p>}
            </div>
          </div>
        ) : configQuery.isError ? (
          <div className="space-y-3">
            <Badge variant="secondary" className="text-[10px]">Not configured</Badge>
            <p className="text-xs text-muted-foreground">Uses default model from environment.</p>
          </div>
        ) : null}
        <div className="mt-3">
          <Button variant="outline" size="sm" className="w-full" onClick={onConfigure}>
            <Settings2 className="mr-1.5 h-3.5 w-3.5" />
            {config ? 'Edit Config' : 'Configure'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
