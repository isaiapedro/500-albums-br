/* Contract-derived browser DTOs. Regenerate from the approved OpenAPI document
 * once Agent 0/4 publishes it; never import ORM or source-provider schemas. */
export type CatalogueAttribution = { source_url: string; source_license: string; attribution_text: string; normalized_content_sha256: string };
export type Album = { id: string; rank: number; title: string; artist_credit: string; release_year: number | null };
export type CataloguePage = { items: Album[]; next_cursor: string | null; catalogue_attribution: CatalogueAttribution };
export type Project = { id: string; name: string; timezone: string };
export type Assignment = { id: string; project_id: string; local_date: string; album: Album; catalogue_attribution: CatalogueAttribution };
export type Rating = { id: string; assignment_id: string; score: number; review: string | null };
export class ApiError extends Error { constructor(public readonly status: number, message: string) { super(message); } }
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) { let message = "The local API could not complete this request."; try { const body: unknown = await response.json(); if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") message = body.detail; } catch { /* provisional API envelope */ } throw new ApiError(response.status, message); }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export const api = {
  albums: () => request<CataloguePage>("/albums"), projects: () => request<Project[]>("/projects"),
  createProject: (name: string, timezone: string) => request<Project>("/projects", { method: "POST", body: JSON.stringify({ name, timezone }) }),
  assignments: (projectId: string) => request<Assignment[]>(`/projects/${projectId}/assignments`),
  generateAssignment: (projectId: string) => request<Assignment>(`/projects/${projectId}/assignments/generate`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() } }),
  saveRating: (assignmentId: string, score: number, review: string) => request<Rating>(`/assignments/${assignmentId}/rating`, { method: "PUT", body: JSON.stringify({ score, review: review || undefined }) }),
};
