export type ApiError = Error & { status?: number };

function buildError(status: number, detail: unknown): ApiError {
  const message =
    typeof detail === "string"
      ? detail
      : detail && typeof detail === "object" && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Request failed (${status})`;

  const error = new Error(message) as ApiError;
  error.status = status;
  return error;
}

export type Project = {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type UploadResponse = {
  job_id: string;
  asset_id: string;
  project_id: string;
  status: string;
  file_path: string;
  mime_type: string;
  size_bytes: number;
  conf_threshold: number;
  iou_threshold: number;
};

export type Detection = {
  id: number;
  class_id: number;
  class_name: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number;
  created_at: string;
};

export type JobDetail = {
  id: string;
  project_id: string;
  status: string;
  input_type: string;
  error_message: string | null;
  conf_threshold: number;
  iou_threshold: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  metrics: {
    tree_count: number;
    avg_confidence: number;
    duration_ms: number;
  } | null;
  detections: Detection[];
  assets: {
    input_image: string | null;
    annotated_image: string | null;
    csv_download_url: string;
    json_download_url: string;
  };
};

export async function apiRequest<T>(
  path: string,
  options?: {
    method?: "GET" | "POST" | "DELETE";
    token?: string;
    body?: unknown;
    formData?: FormData;
  }
): Promise<T> {
  const headers = new Headers();
  if (options?.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  let body: BodyInit | undefined;
  if (options?.formData) {
    body = options.formData;
  } else if (options?.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  const response = await fetch(`/api-proxy${path}`, {
    method: options?.method ?? "GET",
    headers,
    body,
    cache: "no-store"
  });

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    throw buildError(response.status, payload);
  }

  return payload as T;
}

export async function downloadArtifact(path: string, token: string): Promise<void> {
  const response = await fetch(`/api-proxy${path}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store"
  });

  if (!response.ok) {
    const detail = await response.text();
    throw buildError(response.status, detail);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  const filename = filenameMatch?.[1] ?? "download.bin";

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function fetchImageBlobUrl(path: string, token: string): Promise<string> {
  const response = await fetch(`/api-proxy${path}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store"
  });

  if (!response.ok) {
    const detail = await response.text();
    throw buildError(response.status, detail);
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}