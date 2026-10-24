import { json } from "../../_lib.js";

export async function onRequest({ data, next }) {
  if (data.user?.role !== "admin") return json({ error: "admins only" }, 403);
  return next();
}
