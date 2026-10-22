import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { HelperText } from 'react-native-paper';

import { AppText, PrimaryButton } from '@/components/ui';
import { MIN_TOUCH_TARGET, palette, radius, spacing } from '@/theme';
import type { AnswerPhoto } from '@/types/exam';

/** Same limit as the server (MODEL_PAPER_MAX_PHOTOS). */
export const MAX_ANSWER_PHOTOS = 24;
/** Smaller photos upload faster; handwriting stays readable. */
const PHOTO_QUALITY = 0.6;

export interface AnswerPhotosProps {
  photos: AnswerPhoto[];
  onChange: (photos: AnswerPhoto[]) => void;
  disabled?: boolean;
}

function toPhoto(asset: ImagePicker.ImagePickerAsset, n: number): AnswerPhoto {
  return {
    uri: asset.uri,
    mimeType: asset.mimeType ?? 'image/jpeg',
    fileName: asset.fileName ?? `page-${n}.jpg`,
  };
}

/** Take or choose photos of the answer sheets, in page order. */
export function AnswerPhotos({ photos, onChange, disabled = false }: AnswerPhotosProps) {
  const [error, setError] = useState<string | null>(null);
  const room = MAX_ANSWER_PHOTOS - photos.length;

  const add = (assets: ImagePicker.ImagePickerAsset[]): void => {
    const added = assets.slice(0, room).map((asset, i) => toPhoto(asset, photos.length + i + 1));
    onChange([...photos, ...added]);
  };

  const takePhoto = async (): Promise<void> => {
    setError(null);
    try {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        setError('Allow the camera to photograph your answer sheets.');
        return;
      }
      const result = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: PHOTO_QUALITY });
      if (!result.canceled) add(result.assets);
    } catch {
      setError('The camera could not be opened. Try choosing photos instead.');
    }
  };

  const choosePhotos = async (): Promise<void> => {
    setError(null);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsMultipleSelection: true,
        selectionLimit: room,
        orderedSelection: true,
        quality: PHOTO_QUALITY,
      });
      if (!result.canceled) add(result.assets);
    } catch {
      setError('Your photos could not be opened.');
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.buttons}>
        <PrimaryButton
          label="Take photo"
          icon="camera"
          fullWidth={false}
          style={styles.button}
          onPress={() => void takePhoto()}
          disabled={disabled || room <= 0}
          testID="answer-take-photo"
        />
        <PrimaryButton
          label="Choose photos"
          icon="image-multiple"
          mode="outlined"
          fullWidth={false}
          style={styles.button}
          onPress={() => void choosePhotos()}
          disabled={disabled || room <= 0}
        />
      </View>
      {photos.length > 0 ? (
        <>
          <AppText variant="caption" tone="secondary">
            {photos.length} page{photos.length === 1 ? '' : 's'} added, in this order. Tap ✕ to remove one.
          </AppText>
          <View style={styles.grid}>
            {photos.map((photo, i) => (
              <View key={photo.uri} style={styles.thumbWrap}>
                <Image source={{ uri: photo.uri }} style={styles.thumb} contentFit="cover" />
                <AppText variant="caption" style={styles.pageNo}>
                  {i + 1}
                </AppText>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Remove page ${i + 1}`}
                  onPress={() => onChange(photos.filter((p) => p.uri !== photo.uri))}
                  disabled={disabled}
                  style={styles.remove}
                  hitSlop={spacing.sm}
                >
                  <MaterialCommunityIcons name="close" size={18} color={palette.onColor} />
                </Pressable>
              </View>
            ))}
          </View>
        </>
      ) : null}
      {error ? (
        <HelperText type="error" visible>
          {error}
        </HelperText>
      ) : null}
    </View>
  );
}

const THUMB = 88;

const styles = StyleSheet.create({
  container: {
    gap: spacing.md,
  },
  buttons: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  button: {
    flex: 1,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  thumbWrap: {
    width: THUMB,
    height: THUMB * 1.3,
    borderRadius: radius.sm,
    overflow: 'hidden',
    backgroundColor: palette.surfaceMuted,
  },
  thumb: {
    width: '100%',
    height: '100%',
  },
  pageNo: {
    position: 'absolute',
    left: spacing.xs,
    bottom: spacing.xs,
    paddingHorizontal: spacing.xs,
    borderRadius: radius.sm,
    backgroundColor: palette.surface,
  },
  remove: {
    position: 'absolute',
    top: spacing.xs,
    right: spacing.xs,
    width: MIN_TOUCH_TARGET / 2,
    height: MIN_TOUCH_TARGET / 2,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: palette.textPrimary,
  },
});
