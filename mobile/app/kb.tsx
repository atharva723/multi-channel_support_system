import * as DocumentPicker from 'expo-document-picker';
import { useRouter } from 'expo-router';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  Globe,
  Loader,
  RefreshCw,
  Trash2,
  Upload,
  X,
} from 'lucide-react-native';
import React, { useState } from 'react';
import { ActivityIndicator, Alert, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type KbDocument } from '../src/api/client';
import { AppText } from '../src/components/AppText';
import { Button } from '../src/components/Button';
import { Card } from '../src/components/Card';
import { EmptyState } from '../src/components/EmptyState';
import { ErrorState } from '../src/components/ErrorState';
import { ProgressBar } from '../src/components/ProgressBar';
import {
  useAddWebsite,
  useDeleteDocument,
  useKnowledgeBase,
  useReplaceDocument,
  useResyncSource,
  useUploadDocument,
} from '../src/hooks/useKnowledgeBase';
import { useToastStore } from '../src/hooks/useToastStore';
import { relativeTime } from '../src/lib/time';
import { colors, radius, spacing } from '../src/theme';

const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/markdown',
  'text/x-markdown',
];

function StatusPill({ status }: { status: KbDocument['status'] }) {
  const map = {
    ready: { bg: colors.secondaryContainer, fg: colors.primary, label: 'Ready', Icon: CheckCircle2 },
    processing: { bg: '#E7E9FD', fg: colors.actionIndigo, label: 'Processing', Icon: Loader },
    failed: { bg: colors.errorContainer, fg: colors.error, label: 'Failed', Icon: AlertTriangle },
  } as const;
  const s = map[status];
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: s.bg, paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.full }}>
      <s.Icon size={13} color={s.fg} />
      <AppText variant="labelSm" color={s.fg}>
        {s.label}
      </AppText>
    </View>
  );
}

export default function KnowledgeBase() {
  const router = useRouter();
  const { data: docs, isLoading, isError, refetch } = useKnowledgeBase();
  const upload = useUploadDocument();
  const addWebsite = useAddWebsite();
  const resync = useResyncSource();
  const del = useDeleteDocument();
  const replace = useReplaceDocument();
  const showToast = useToastStore((s) => s.show);
  const [picking, setPicking] = useState(false);
  const [replacingId, setReplacingId] = useState<number | null>(null);
  const [webModal, setWebModal] = useState(false);
  const [webUrl, setWebUrl] = useState('');

  const submitWebsite = () => {
    const url = webUrl.trim();
    if (!url) return;
    addWebsite.mutate(url, {
      onSuccess: () => {
        setWebModal(false);
        setWebUrl('');
        showToast('Website added — crawling…', 'email');
      },
      onError: (e: any) => Alert.alert('Couldn\u2019t add website', e?.message ?? 'Please try again.'),
    });
  };

  const doResync = (doc: KbDocument) => {
    resync.mutate(doc.id, {
      onSuccess: () => showToast('Re-crawling website…'),
      onError: (e: any) => Alert.alert('Resync failed', e?.message ?? 'Please try again.'),
    });
  };

  const pickAndReplace = async (doc: KbDocument) => {
    try {
      setReplacingId(doc.id);
      const result = await DocumentPicker.getDocumentAsync({
        type: ACCEPTED_TYPES,
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (result.canceled || !result.assets?.length) return;
      const asset = result.assets[0];
      replace.mutate(
        { id: doc.id, file: { uri: asset.uri, name: asset.name, mimeType: asset.mimeType } },
        {
          onSuccess: () => showToast('Replacing document — embedding…'),
          onError: (e: any) => Alert.alert('Replace failed', e?.message ?? 'Please try again.'),
        },
      );
    } catch (e: any) {
      Alert.alert('Could not pick file', e?.message ?? 'Please try again.');
    } finally {
      setReplacingId(null);
    }
  };

  const pickAndUpload = async () => {
    try {
      setPicking(true);
      const result = await DocumentPicker.getDocumentAsync({
        type: ACCEPTED_TYPES,
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (result.canceled || !result.assets?.length) return;
      const asset = result.assets[0];
      upload.mutate(
        { uri: asset.uri, name: asset.name, mimeType: asset.mimeType },
        {
          onSuccess: () => showToast('Document uploaded — embedding…'),
          onError: (e: any) =>
            Alert.alert('Upload failed', e?.message ?? 'Please try again.'),
        },
      );
    } catch (e: any) {
      Alert.alert('Could not pick file', e?.message ?? 'Please try again.');
    } finally {
      setPicking(false);
    }
  };

  const confirmDelete = (doc: KbDocument) => {
    Alert.alert('Remove document', `Delete "${doc.title}" from the knowledge base?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () =>
          del.mutate(doc.id, { onSuccess: () => showToast('Document removed') }),
      },
    ]);
  };

  const list = docs ?? [];

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.page, paddingVertical: spacing.md }}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <ArrowLeft size={26} color={colors.onSurface} />
        </Pressable>
        <AppText variant="titleMd" color={colors.primary}>
          Knowledge Base
        </AppText>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.page, gap: spacing.lg, paddingBottom: spacing.xxxl }}>
        <View style={{ gap: spacing.sm }}>
          <AppText variant="headlineLg">Ground replies in your info</AppText>
          <AppText variant="bodyMd" color={colors.onSurfaceVariant}>
            Add documents (PDF, DOCX, TXT, MD) or your business website. Uploading
            adds to your knowledge base; use Replace on a document to overwrite an
            outdated one. The AI answers only from this content.
          </AppText>
        </View>

        <View style={{ flexDirection: 'row', gap: spacing.base }}>
          <View style={{ flex: 1 }}>
            <Button
              label={picking || upload.isPending ? 'Uploading…' : 'Upload doc'}
              loading={picking || upload.isPending}
              icon={<Upload size={18} color={colors.onPrimary} />}
              onPress={pickAndUpload}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Button
              label="Add website"
              variant="ghost"
              icon={<Globe size={18} color={colors.primary} />}
              onPress={() => setWebModal(true)}
            />
          </View>
        </View>

        <AppText variant="labelMd" color={colors.primary} style={{ textTransform: 'uppercase' }}>
          Sources
        </AppText>

        {isLoading ? (
          <View style={{ alignItems: 'center', paddingVertical: spacing.xl }}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : isError ? (
          <ErrorState
            title="Couldn't load documents"
            message="We couldn't reach the server. Try again."
            onRetry={refetch}
          />
        ) : list.length === 0 ? (
          <EmptyState
            icon={<FileText size={40} color={colors.primary} />}
            title="No documents yet"
            subtitle="Upload your first document to give the AI a knowledge base to answer from."
          />
        ) : (
          list.map((doc) => (
            <Card key={doc.id} style={{ gap: spacing.md }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.md }}>
                <View style={{ width: 44, height: 44, borderRadius: radius.md, backgroundColor: colors.secondaryContainer, alignItems: 'center', justifyContent: 'center' }}>
                  {doc.source === 'upload' ? (
                    <FileText size={22} color={colors.primary} />
                  ) : (
                    <Globe size={22} color={colors.primary} />
                  )}
                </View>
                <View style={{ flex: 1 }}>
                  <AppText variant="titleSm" numberOfLines={1}>
                    {doc.title}
                  </AppText>
                  <AppText variant="labelSm" color={colors.outline}>
                    {doc.source === 'upload' ? 'Uploaded' : `Synced · ${doc.source}`}
                    {doc.status === 'ready' ? ` · ${doc.chunk_count} chunks` : ''} ·{' '}
                    {relativeTime(doc.created_at)}
                  </AppText>
                </View>
              </View>

              {doc.status === 'processing' ? (
                <ProgressBar
                  indeterminate={doc.chunk_total === 0}
                  value={doc.chunk_total > 0 ? (doc.chunk_count / doc.chunk_total) * 100 : 0}
                  label={
                    doc.chunk_total === 0
                      ? doc.source === 'web'
                        ? 'Reading website…'
                        : 'Preparing document…'
                      : doc.chunk_count >= doc.chunk_total
                        ? 'Finishing up…'
                        : 'Embedding your data…'
                  }
                />
              ) : null}

              {doc.status === 'failed' && doc.error ? (
                <AppText variant="labelSm" color={colors.error} numberOfLines={2}>
                  {doc.error}
                </AppText>
              ) : null}

              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <StatusPill status={doc.status} />
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
                  {doc.source === 'web' ? (
                    <Pressable
                      onPress={() => doResync(doc)}
                      disabled={doc.status === 'processing'}
                      hitSlop={8}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: radius.full, backgroundColor: colors.secondaryContainer, opacity: doc.status === 'processing' ? 0.5 : 1 }}
                    >
                      <RefreshCw size={14} color={colors.primary} />
                      <AppText variant="labelMd" color={colors.primary}>
                        Refresh
                      </AppText>
                    </Pressable>
                  ) : (
                    <Pressable
                      onPress={() => pickAndReplace(doc)}
                      disabled={doc.status === 'processing' || replacingId === doc.id}
                      hitSlop={8}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: radius.full, backgroundColor: colors.secondaryContainer, opacity: doc.status === 'processing' ? 0.5 : 1 }}
                    >
                      <RefreshCw size={14} color={colors.primary} />
                      <AppText variant="labelMd" color={colors.primary}>
                        Replace
                      </AppText>
                    </Pressable>
                  )}
                  <Pressable
                    onPress={() => confirmDelete(doc)}
                    hitSlop={8}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: radius.full, backgroundColor: colors.errorContainer }}
                  >
                    <Trash2 size={14} color={colors.error} />
                    <AppText variant="labelMd" color={colors.error}>
                      Remove
                    </AppText>
                  </Pressable>
                </View>
              </View>
            </Card>
          ))
        )}
      </ScrollView>

      <Modal visible={webModal} transparent animationType="fade" onRequestClose={() => setWebModal(false)}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', padding: spacing.page }}
        >
          <Card style={{ gap: spacing.base }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <AppText variant="titleMd">Add a website</AppText>
              <Pressable onPress={() => setWebModal(false)} hitSlop={10}>
                <X size={22} color={colors.outline} />
              </Pressable>
            </View>
            <AppText variant="bodyMd" color={colors.onSurfaceVariant}>
              Paste your business site or a policy/FAQ page. We&apos;ll pull the useful
              content (skipping menus and footers) and keep it in sync.
            </AppText>
            <TextInput
              value={webUrl}
              onChangeText={setWebUrl}
              placeholder="https://yourbusiness.com"
              placeholderTextColor={colors.outline}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              autoFocus
              onSubmitEditing={submitWebsite}
              style={{
                backgroundColor: colors.cardMuted,
                borderRadius: radius.md,
                paddingHorizontal: spacing.base,
                height: 50,
                fontFamily: 'HankenGrotesk_400Regular',
                fontSize: 16,
                color: colors.onSurface,
              }}
            />
            <Button
              label={addWebsite.isPending ? 'Adding…' : 'Add website'}
              loading={addWebsite.isPending}
              icon={<Globe size={18} color={colors.onPrimary} />}
              onPress={submitWebsite}
            />
          </Card>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}
