<template>
  <div class="login-container">
    <div class="login-box">
      <h2>Access Required</h2>
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label for="accessCode">Access Code</label>
          <input
            type="password"
            id="accessCode"
            v-model="accessCode"
            required
            placeholder="Enter access code"
          />
        </div>
        <div v-if="error" class="error-message">{{ error }}</div>
        <button type="submit" :disabled="loading">
          {{ loading ? "Verifying..." : "Access" }}
        </button>
      </form>
    </div>
  </div>
</template>

<script>
export default {
  name: "Login",
  emits: ["login-success"],
  data() {
    return {
      accessCode: "",
      error: null,
      loading: false,
    };
  },
  methods: {
    async handleLogin() {
      this.error = null;
      this.loading = true;

      try {
        // Store access code in localStorage for subsequent requests
        if (this.accessCode === "frankenstein") {
          localStorage.setItem("accessCode", this.accessCode);
          this.$emit("login-success", this.accessCode);
        } else {
          this.error = "Invalid access code";
        }
      } catch (err) {
        this.error = "Failed to verify access code";
      } finally {
        this.loading = false;
      }
    },
  },
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f5f5f5;
}

.login-box {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
}

.form-group {
  margin-bottom: 1rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

button {
  width: 100%;
  padding: 0.75rem;
  background-color: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
}

button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

.error-message {
  color: #ff0033;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}
</style>
