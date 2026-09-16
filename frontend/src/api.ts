let csrf = "";
export const setCsrf = (token: string) => {
  csrf = token;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T = void>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (method !== "GET" && csrf) headers["X-CSRF-Token"] = csrf;
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers,
    cache: "no-store",
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "服务暂时不可用，请稍后重试" }));
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail)
          ? body.detail.map((v: { msg: string }) => v.msg).join("；")
          : "请求失败";
    throw new ApiError(detail, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function uploadPoster(path: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  const headers: Record<string, string> = {};
  if (csrf) headers["X-CSRF-Token"] = csrf;
  const response = await fetch(`/api${path}`, {
    method: "PUT",
    credentials: "same-origin",
    headers,
    cache: "no-store",
    body: form,
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "上传失败，请重试" }));
    throw new ApiError(
      typeof body.detail === "string" ? body.detail : "上传失败",
      response.status,
    );
  }
}
