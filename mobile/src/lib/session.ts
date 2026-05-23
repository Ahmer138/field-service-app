import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'field-service-mobile-token';

export async function loadStoredToken() {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function saveStoredToken(token: string) {
  return SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearStoredToken() {
  return SecureStore.deleteItemAsync(TOKEN_KEY);
}
