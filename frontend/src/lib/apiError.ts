type ApiErrorDetails = Record<string, unknown>;

type ApiErrorInfo = {
  code: string;
  message: string;
  details: ApiErrorDetails;
};

type BuildUserFacingApiErrorMessageOptions = {
  errorPayload: unknown;
  statusCode: number;
  fallbackMessage: string;
  userMessageByCode?: Record<string, string>;
};

const DEFAULT_USER_MESSAGE_BY_CODE: Record<string, string> = {
  BAD_REQUEST: "リクエスト内容が不正です。",
  VALIDATION_ERROR: "入力内容が不正です。",
  INVALID_ISBN: "ISBN の形式が不正です。",
  SERIES_NOT_FOUND: "対象のシリーズが見つかりません。",
  VOLUME_NOT_FOUND: "対象の巻が見つかりません。",
  VOLUME_ALREADY_EXISTS: "この巻は既に登録されています。",
  CATALOG_ITEM_NOT_FOUND: "該当する書誌情報が見つかりません。",
  NDL_API_TIMEOUT: "外部サービスが混み合っています。時間をおいて再試行してください。",
  NDL_API_BAD_GATEWAY: "外部サービスとの通信に失敗しました。時間をおいて再試行してください。",
  SERVICE_UNAVAILABLE: "サービスが一時的に利用できません。時間をおいて再試行してください。",
  INTERNAL_SERVER_ERROR: "サーバーでエラーが発生しました。時間をおいて再試行してください。",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function extractApiErrorInfo(errorPayload: unknown): ApiErrorInfo | null {
  if (!isRecord(errorPayload)) {
    return null;
  }

  const errorValue = errorPayload.error;
  if (!isRecord(errorValue)) {
    return null;
  }

  if (typeof errorValue.code !== "string" || typeof errorValue.message !== "string") {
    return null;
  }

  const normalizedCode = errorValue.code.trim();
  if (normalizedCode === "") {
    return null;
  }

  const normalizedMessage = errorValue.message.trim();
  const normalizedDetails = isRecord(errorValue.details) ? errorValue.details : {};

  return {
    code: normalizedCode,
    message: normalizedMessage,
    details: normalizedDetails,
  };
}

export function extractApiErrorCode(errorPayload: unknown): string | null {
  const parsedError = extractApiErrorInfo(errorPayload);
  if (parsedError === null) {
    return null;
  }

  return parsedError.code;
}

export function buildUserFacingApiErrorMessage({
  errorPayload,
  statusCode,
  fallbackMessage,
  userMessageByCode,
}: BuildUserFacingApiErrorMessageOptions): string {
  const parsedError = extractApiErrorInfo(errorPayload);
  if (parsedError === null) {
    return `${fallbackMessage} (status: ${statusCode})`;
  }

  if (userMessageByCode !== undefined) {
    const customMessage = userMessageByCode[parsedError.code];
    if (typeof customMessage === "string" && customMessage.trim() !== "") {
      return customMessage.trim();
    }
  }

  const defaultMessage = DEFAULT_USER_MESSAGE_BY_CODE[parsedError.code];
  if (typeof defaultMessage === "string" && defaultMessage.trim() !== "") {
    return defaultMessage.trim();
  }

  if (parsedError.message !== "") {
    return parsedError.message;
  }

  return `${fallbackMessage} (status: ${statusCode}, code: ${parsedError.code})`;
}
