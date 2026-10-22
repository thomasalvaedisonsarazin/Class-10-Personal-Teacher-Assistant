import { File, Paths } from 'expo-file-system';
import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';
import { Platform } from 'react-native';

import { pdfFileName } from '@/lib/exam';
import type { PaperDocument } from '@/types/exam';

/** Turns the paper's HTML into a PDF and opens the share sheet (save to Files, WhatsApp, Drive…). */
export async function sharePaperPdf(doc: PaperDocument): Promise<void> {
  if (Platform.OS === 'web') {
    await Print.printAsync({ html: doc.html });
    return;
  }
  const { uri } = await Print.printToFileAsync({ html: doc.html });
  const target = new File(Paths.cache, pdfFileName(doc.fileName));
  if (target.exists) target.delete();
  new File(uri).move(target);
  await Sharing.shareAsync(target.uri, { mimeType: 'application/pdf', dialogTitle: target.name, UTI: 'com.adobe.pdf' });
}

/** Opens the phone's print screen (it also offers "Save as PDF"). */
export async function printPaper(doc: PaperDocument): Promise<void> {
  await Print.printAsync({ html: doc.html });
}
