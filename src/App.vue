const requester = buildRequester({
  baseUrl: import.meta.env.VITE_API_URL || "http://localhost:8006/api",
  headers: {
    Accept: "application/json",
  },
  fetchParams: {
    credentials: "include",
  }
});