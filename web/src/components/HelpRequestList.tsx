import type { HelpRequest } from "../types";
export function HelpRequestList({requests}:{requests:HelpRequest[]}) { return <ul>{requests.map(request=><li key={request.request_id}>{request.status} · {new Date(request.created_at_ms).toLocaleString()}</li>)}</ul>; }
