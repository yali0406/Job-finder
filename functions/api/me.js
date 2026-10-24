import { json } from "../_lib.js";

export const onRequestGet = ({ data }) => json(data.user);
