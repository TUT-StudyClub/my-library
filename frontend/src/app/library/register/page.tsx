"use client";

import { BrowserMultiFormatReader, type IScannerControls } from "@zxing/browser";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./page.module.css";

const DEFAULT_CAMERA_ERROR_MESSAGE =
  "カメラを起動できませんでした。ブラウザの権限設定を確認してください。";
const UNSUPPORTED_CAMERA_MESSAGE = "このブラウザではカメラ機能を利用できません。";
const SCANNER_ERROR_MESSAGE = "読み取り処理でエラーが発生しました。";
const IGNORABLE_SCAN_ERROR_NAMES = new Set([
  "NotFoundException",
  "ChecksumException",
  "FormatException",
]);

export default function RegisterPage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const readerRef = useRef<BrowserMultiFormatReader | null>(null);
  const scannerControlsRef = useRef<IScannerControls | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [isStartingCamera, setIsStartingCamera] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const stopCamera = useCallback(() => {
    scannerControlsRef.current?.stop();
    scannerControlsRef.current = null;

    if (videoRef.current !== null) {
      const sourceObject = videoRef.current.srcObject;
      if (sourceObject instanceof MediaStream) {
        sourceObject.getTracks().forEach((track) => {
          track.stop();
        });
      }
      videoRef.current.srcObject = null;
    }

    setIsCameraActive(false);
    setIsStartingCamera(false);
  }, []);

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  const startCamera = useCallback(async () => {
    if (isCameraActive || isStartingCamera || videoRef.current === null) {
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setErrorMessage(UNSUPPORTED_CAMERA_MESSAGE);
      return;
    }

    setErrorMessage(null);
    setIsStartingCamera(true);

    try {
      if (readerRef.current === null) {
        readerRef.current = new BrowserMultiFormatReader();
      }

      const scannerControls = await readerRef.current.decodeFromVideoDevice(
        undefined,
        videoRef.current,
        (result, error) => {
          if (result !== undefined) {
            setScanResult(result.getText());
          }

          if (error !== undefined && !IGNORABLE_SCAN_ERROR_NAMES.has(error.name)) {
            setErrorMessage(SCANNER_ERROR_MESSAGE);
          }
        }
      );

      scannerControlsRef.current = scannerControls;
      setIsCameraActive(true);
    } catch {
      stopCamera();
      setErrorMessage(DEFAULT_CAMERA_ERROR_MESSAGE);
    } finally {
      setIsStartingCamera(false);
    }
  }, [isCameraActive, isStartingCamera, stopCamera]);

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <p className={styles.backLinkWrapper}>
          <Link className={styles.backLink} href="/library">
            ライブラリへ戻る
          </Link>
        </p>

        <header className={styles.header}>
          <h1 className={styles.title}>登録</h1>
          <p className={styles.description}>
            カメラを起動してバーコードを読み取り、登録用のISBNを取得します。
          </p>
        </header>

        <section className={styles.scannerPanel}>
          <h2 className={styles.sectionTitle}>バーコード読み取り</h2>
          <p className={styles.sectionDescription}>
            カメラ起動後に本のバーコードをプレビュー中央へ合わせてください。
          </p>

          <div className={styles.previewFrame}>
            <video
              aria-label="カメラプレビュー"
              autoPlay
              className={styles.cameraPreview}
              muted
              playsInline
              ref={videoRef}
            />
            {!isCameraActive && (
              <p className={styles.previewHint}>カメラ起動でプレビューを表示します。</p>
            )}
          </div>

          <div className={styles.actionRow}>
            <button
              className={styles.primaryButton}
              disabled={isCameraActive || isStartingCamera}
              onClick={() => {
                void startCamera();
              }}
              type="button"
            >
              {isStartingCamera ? "起動中..." : "カメラ起動"}
            </button>
            <button
              className={styles.secondaryButton}
              disabled={!isCameraActive}
              onClick={stopCamera}
              type="button"
            >
              カメラ停止
            </button>
          </div>

          {errorMessage !== null && (
            <p aria-live="polite" className={styles.errorText} role="status">
              {errorMessage}
            </p>
          )}

          <div className={styles.resultPanel}>
            <p className={styles.resultLabel}>読み取り結果</p>
            <p className={styles.resultValue}>{scanResult ?? "未検出"}</p>
          </div>
        </section>
      </div>
    </main>
  );
}
