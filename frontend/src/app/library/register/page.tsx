"use client";

import { BrowserMultiFormatReader, type IScannerControls } from "@zxing/browser";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./page.module.css";

const DEFAULT_CAMERA_ERROR_MESSAGE =
  "カメラを起動できませんでした。ブラウザの権限設定を確認してください。";
const UNSUPPORTED_CAMERA_MESSAGE = "このブラウザではカメラ機能を利用できません。";
const SCANNER_ERROR_MESSAGE = "読み取り処理でエラーが発生しました。";
const ISBN_EXTRACTION_ERROR_MESSAGE =
  "読み取り文字列からISBNを抽出できませんでした。別の角度で再読み取りしてください。";
const INVALID_ISBN_MESSAGE = "ISBNは正規化後に13桁の数字である必要があります。";
const DEFAULT_REGISTER_ERROR_MESSAGE = "登録に失敗しました。";
const REGISTER_REQUEST_ERROR_MESSAGE = "登録リクエストの送信に失敗しました。";
const REGISTER_SUCCESS_MESSAGE = "登録完了";
const REGISTER_ALREADY_EXISTS_MESSAGE = "このISBNは既に登録済みです。";
const REGISTER_IGNORED_RECENT_MESSAGE =
  "同じISBNを連続登録しないため、しばらく待ってから再実行してください。";
const RECENT_PROCESSED_ISBN_IGNORE_MILLISECONDS = 10_000;
const IGNORABLE_SCAN_ERROR_NAMES = new Set([
  "NotFoundException",
  "ChecksumException",
  "FormatException",
]);
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type RegisterRequestStatus =
  | "idle"
  | "success"
  | "alreadyExists"
  | "recentlyProcessed"
  | "invalidIsbn"
  | "failure";
type ProgressTone = "neutral" | "success" | "warning" | "error";

function normalizeScannedText(rawText: string): string {
  return rawText.normalize("NFKC").trim();
}

function toNormalizedIsbn(rawText: string): string | null {
  const normalizedText = normalizeScannedText(rawText);
  const compactText = normalizedText.replaceAll("-", "").replace(/\s+/g, "");
  if (isNormalizedIsbn(compactText)) {
    return compactText;
  }

  return null;
}

function isNormalizedIsbn(value: string): boolean {
  return /^[0-9]{13}$/.test(value);
}

function extractRegisterErrorMessage(errorPayload: unknown, statusCode: number): string {
  if (
    typeof errorPayload === "object" &&
    errorPayload !== null &&
    "error" in errorPayload &&
    typeof errorPayload.error === "object" &&
    errorPayload.error !== null &&
    "message" in errorPayload.error &&
    typeof errorPayload.error.message === "string"
  ) {
    const message = errorPayload.error.message.trim();
    if (message !== "") {
      return message;
    }
  }

  return `${DEFAULT_REGISTER_ERROR_MESSAGE} (status: ${statusCode})`;
}

function extractRegisterErrorCode(errorPayload: unknown): string | null {
  if (
    typeof errorPayload === "object" &&
    errorPayload !== null &&
    "error" in errorPayload &&
    typeof errorPayload.error === "object" &&
    errorPayload.error !== null &&
    "code" in errorPayload.error &&
    typeof errorPayload.error.code === "string"
  ) {
    const errorCode = errorPayload.error.code.trim();
    if (errorCode !== "") {
      return errorCode;
    }
  }

  return null;
}

function extractRegisteredIsbn(payload: unknown): string | null {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "volume" in payload &&
    typeof payload.volume === "object" &&
    payload.volume !== null &&
    "isbn" in payload.volume &&
    typeof payload.volume.isbn === "string"
  ) {
    const normalizedIsbn = payload.volume.isbn.trim();
    if (normalizedIsbn !== "") {
      return normalizedIsbn;
    }
  }

  return null;
}

function extractNormalizedIsbn(scanText: string): string | null {
  const directMatchIsbn = toNormalizedIsbn(scanText);
  if (directMatchIsbn !== null) {
    return directMatchIsbn;
  }

  const normalizedScanText = normalizeScannedText(scanText);
  const possibleIsbnTokens = normalizedScanText.match(/[0-9][0-9\-\s]{11,30}[0-9]/g) ?? [];

  for (const token of possibleIsbnTokens) {
    const normalizedIsbn = toNormalizedIsbn(token);
    if (normalizedIsbn !== null) {
      return normalizedIsbn;
    }
  }

  return null;
}

export default function RegisterPage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const readerRef = useRef<BrowserMultiFormatReader | null>(null);
  const scannerControlsRef = useRef<IScannerControls | null>(null);
  const latestScanTextRef = useRef<string | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [isStartingCamera, setIsStartingCamera] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [confirmedIsbn, setConfirmedIsbn] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isbnErrorMessage, setIsbnErrorMessage] = useState<string | null>(null);
  const isSubmittingRegisterRef = useRef(false);
  const latestProcessedIsbnRef = useRef<string | null>(null);
  const latestProcessedAtMillisecondsRef = useRef(0);
  const [isSubmittingRegister, setIsSubmittingRegister] = useState(false);
  const [registerRequestStatus, setRegisterRequestStatus] = useState<RegisterRequestStatus>("idle");
  const [registerRequestMessage, setRegisterRequestMessage] = useState<string | null>(null);
  const registerRequestPayload =
    confirmedIsbn === null
      ? null
      : JSON.stringify(
          {
            isbn: confirmedIsbn,
          },
          null,
          2
        );
  let progressStatusLabel = "待機中";
  let nextActionLabel = "「カメラ起動」を押してください。";
  let progressTone: ProgressTone = "neutral";

  if (errorMessage !== null) {
    progressStatusLabel = "カメラ利用不可";
    nextActionLabel = "ブラウザのカメラ権限を確認して、再度「カメラ起動」を押してください。";
    progressTone = "error";
  } else if (isStartingCamera) {
    progressStatusLabel = "カメラ起動中";
    nextActionLabel = "プレビューが表示されるまで待ってください。";
    progressTone = "neutral";
  } else if (!isCameraActive) {
    progressStatusLabel = "カメラ未起動";
    nextActionLabel = "「カメラ起動」を押してバーコード読み取りを開始してください。";
    progressTone = "neutral";
  } else if (isSubmittingRegister) {
    progressStatusLabel = "登録API実行中";
    nextActionLabel = "完了までそのまま待ってください。";
    progressTone = "neutral";
  } else if (registerRequestStatus === "success") {
    progressStatusLabel = "登録完了";
    nextActionLabel =
      "続けて登録する場合は次のバーコードを読み取って「登録する」を押してください。";
    progressTone = "success";
  } else if (registerRequestStatus === "alreadyExists") {
    progressStatusLabel = "登録済みISBN";
    nextActionLabel = "別の本を登録する場合はバーコードを読み替えてください。";
    progressTone = "warning";
  } else if (registerRequestStatus === "recentlyProcessed") {
    progressStatusLabel = "同一ISBN待機中";
    nextActionLabel = "同じISBNは10秒間無視されます。時間をおいて再実行してください。";
    progressTone = "warning";
  } else if (registerRequestStatus === "failure") {
    progressStatusLabel = "登録失敗";
    nextActionLabel = "通信状況を確認し、同じISBNでもう一度「登録する」を押してください。";
    progressTone = "error";
  } else if (confirmedIsbn !== null) {
    progressStatusLabel = "ISBN確定済み";
    nextActionLabel = "内容を確認して「登録する」を押してください。";
    progressTone = "success";
  } else if (isbnErrorMessage !== null) {
    progressStatusLabel = "ISBN未確定";
    nextActionLabel = "バーコードの角度や距離を変えて、再度読み取ってください。";
    progressTone = "warning";
  } else if (scanResult !== null) {
    progressStatusLabel = "読み取り中";
    nextActionLabel = "ISBNが13桁で確定するまでバーコードを合わせ続けてください。";
    progressTone = "neutral";
  } else {
    progressStatusLabel = "バーコード待機中";
    nextActionLabel = "プレビュー中央にバーコードを合わせてください。";
    progressTone = "neutral";
  }
  const progressToneClassName =
    progressTone === "success"
      ? styles.progressPanelSuccess
      : progressTone === "warning"
        ? styles.progressPanelWarning
        : progressTone === "error"
          ? styles.progressPanelError
          : styles.progressPanelNeutral;

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
    setIsbnErrorMessage(null);
    setIsStartingCamera(true);
    latestScanTextRef.current = null;

    try {
      if (readerRef.current === null) {
        readerRef.current = new BrowserMultiFormatReader();
      }

      const scannerControls = await readerRef.current.decodeFromVideoDevice(
        undefined,
        videoRef.current,
        (result, error) => {
          if (result !== undefined) {
            const currentScanText = result.getText();
            if (latestScanTextRef.current !== currentScanText) {
              latestScanTextRef.current = currentScanText;
              setScanResult(currentScanText);

              const extractedIsbn = extractNormalizedIsbn(currentScanText);
              if (extractedIsbn !== null) {
                setConfirmedIsbn(extractedIsbn);
                setIsbnErrorMessage(null);
              } else {
                setConfirmedIsbn(null);
                setIsbnErrorMessage(ISBN_EXTRACTION_ERROR_MESSAGE);
              }
            }
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

  const submitRegisterRequest = useCallback(async () => {
    if (isSubmittingRegisterRef.current) {
      return;
    }

    if (confirmedIsbn === null || !isNormalizedIsbn(confirmedIsbn)) {
      setRegisterRequestStatus("invalidIsbn");
      setRegisterRequestMessage(INVALID_ISBN_MESSAGE);
      return;
    }

    const nowMilliseconds = Date.now();
    const isDuplicateWithinIgnoreWindow =
      latestProcessedIsbnRef.current === confirmedIsbn &&
      nowMilliseconds - latestProcessedAtMillisecondsRef.current <
        RECENT_PROCESSED_ISBN_IGNORE_MILLISECONDS;
    if (isDuplicateWithinIgnoreWindow) {
      setRegisterRequestStatus("recentlyProcessed");
      setRegisterRequestMessage(REGISTER_IGNORED_RECENT_MESSAGE);
      return;
    }

    const requestIsbn = confirmedIsbn;
    isSubmittingRegisterRef.current = true;
    setRegisterRequestStatus("idle");
    setRegisterRequestMessage(null);
    setIsSubmittingRegister(true);

    try {
      const response = await fetch(new URL("/api/volumes", API_BASE_URL).toString(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          isbn: requestIsbn,
        }),
      });
      latestProcessedIsbnRef.current = requestIsbn;
      latestProcessedAtMillisecondsRef.current = Date.now();

      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as unknown;
        const registerErrorCode = extractRegisterErrorCode(errorPayload);
        if (response.status === 409 && registerErrorCode === "VOLUME_ALREADY_EXISTS") {
          setRegisterRequestStatus("alreadyExists");
          setRegisterRequestMessage(REGISTER_ALREADY_EXISTS_MESSAGE);
          return;
        }

        if (response.status === 400 && registerErrorCode === "INVALID_ISBN") {
          setRegisterRequestStatus("invalidIsbn");
          setRegisterRequestMessage(INVALID_ISBN_MESSAGE);
          return;
        }

        setRegisterRequestStatus("failure");
        setRegisterRequestMessage(extractRegisterErrorMessage(errorPayload, response.status));
        return;
      }

      const successPayload = (await response.json().catch(() => null)) as unknown;
      const registeredIsbn = extractRegisteredIsbn(successPayload) ?? requestIsbn;
      setRegisterRequestStatus("success");
      setRegisterRequestMessage(`${REGISTER_SUCCESS_MESSAGE}（ISBN: ${registeredIsbn}）`);
    } catch {
      setRegisterRequestStatus("failure");
      setRegisterRequestMessage(REGISTER_REQUEST_ERROR_MESSAGE);
    } finally {
      isSubmittingRegisterRef.current = false;
      setIsSubmittingRegister(false);
    }
  }, [confirmedIsbn]);

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
          <div className={`${styles.progressPanel} ${progressToneClassName}`}>
            <p className={styles.progressLabel}>現在状態</p>
            <p className={styles.progressValue}>{progressStatusLabel}</p>
            <p className={styles.progressLabel}>次にすること</p>
            <p className={styles.progressGuide}>{nextActionLabel}</p>
          </div>

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

          <div className={styles.resultPanel}>
            <p className={styles.resultLabel}>登録対象ISBN（正規化済み）</p>
            <p className={styles.resultValue}>{confirmedIsbn ?? "未確定"}</p>
            <p className={styles.resultDescription}>
              前後空白除去・全角半角正規化・ハイフン除去後の13桁のみを登録対象にします。
            </p>
          </div>

          {isbnErrorMessage !== null && (
            <p aria-live="polite" className={styles.errorText} role="status">
              {isbnErrorMessage}
            </p>
          )}

          <div className={styles.payloadPanel}>
            <p className={styles.resultLabel}>登録処理へ渡すデータ</p>
            <pre className={styles.payloadValue}>
              {registerRequestPayload ?? "ISBNを確定すると登録リクエストを生成できます。"}
            </pre>
          </div>

          <div className={styles.submitRow}>
            <button
              className={styles.submitButton}
              disabled={isSubmittingRegister}
              onClick={() => {
                void submitRegisterRequest();
              }}
              type="button"
            >
              {isSubmittingRegister ? "登録中..." : "登録する"}
            </button>
          </div>

          {registerRequestMessage !== null && (
            <p
              aria-live="polite"
              className={
                registerRequestStatus === "success"
                  ? styles.successText
                  : registerRequestStatus === "alreadyExists" ||
                      registerRequestStatus === "recentlyProcessed"
                    ? styles.infoText
                    : styles.errorText
              }
              role="status"
            >
              {registerRequestMessage}
            </p>
          )}
        </section>
      </div>
    </main>
  );
}
