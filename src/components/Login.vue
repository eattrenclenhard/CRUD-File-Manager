<template>
  <div class="login-container">
    <div class="login-box">
      <h2>Frankenstein File Manager</h2>
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <input
            type="password"
            id="accessCode"
            v-model="accessCode"
            required
            title="fill in access code"
            placeholder="Enter access code"
            autocomplete="current-password"
          />
        </div>
        <div v-if="error" class="error-message" role="alert">
          <p>{{ error }}</p>
        </div>
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
        const response = await fetch("http://localhost:8006/api/login", {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
          },
          body: JSON.stringify({ accessCode: this.accessCode }),
        });

        const data = await response.json();
        
        if (!response.ok) {
          // Display both status code and error message if available
          this.error = `Error ${response.status}: ${data.error || response.statusText}`;
          console.error('Login error:', data);
          return;
        }

        this.$emit("login-success");
      } catch (err) {
        console.error('Login error:', err);
        this.error = `Connection error: ${err.message}`;
      } finally {
        this.loading = false;
        this.accessCode = "";
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
  margin: 0 auto;
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-left: auto;
  margin-right: auto;
}

form {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.form-group {
  margin-bottom: 1rem;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

input {
  width: 100%;
  max-width: 250px;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

button {
  width: auto;
  min-width: 80px;
  padding: 0.75rem 1.25rem;
  background-color: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  display: block;
  margin-left: auto;
  margin-right: auto;
}

button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

.error-message {
  color: #ff0033;
  margin: 1rem 0;
  padding: 0.5rem;
  border-radius: 4px;
  background-color: #ffebee;
  border: 1px solid #ffcdd2;
  font-size: 0.9rem;
  width: 100%;
  max-width: 250px;
  text-align: center;
}

.error-message p {
  margin: 0;
  word-break: break-word;
}
</style>
