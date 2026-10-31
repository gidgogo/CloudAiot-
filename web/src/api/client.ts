import type { ApiEnvelope, Device, HelpRequest } from "../types";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
async function request<T>(path:string, init:RequestInit={}) : Promise<T> {
 const csrf=document.cookie.split("; ").find(v=>v.startsWith("aiot_csrf_token="))?.split("=")[1];
 const response=await fetch(API_BASE_URL+path,{...init,credentials:"include",headers:{"Content-Type":"application/json",...(csrf?{"X-CSRF-Token":csrf}:{}),...init.headers}});
 if(!response.ok) throw new Error(await response.text());
 return (await response.json() as ApiEnvelope<T>).data;
}
export const api={ devices:()=>request<Device[]>("/devices"), helpRequests:()=>request<HelpRequest[]>("/help-requests"), createHelp:(user_id:string)=>request<HelpRequest>("/help-requests",{method:"POST",body:JSON.stringify({user_id})}) };
export { API_BASE_URL };
