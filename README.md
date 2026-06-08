# RLBmods Reseller API Integration Guide 🚀

Welcome to the **RLBmods Reseller API**! This API allows approved resellers to programmatically check product status, purchase and generate license keys, reset HWIDs, and monitor their wallet balance directly from their own stores, bots, or applications.

---

## 🔑 1.1 Getting Your API Key

Before you can make requests to the API, you need to generate a secure Reseller API Key from your workspace dashboard.

1. Log in to your RLBmods Reseller account.
2. Navigate to **Team Workspaces** from the sidebar.
3. Select the Workspace you want to use.
4. Scroll down to the **API Access** section and click **Generate API Key**.

![Where to get your API Key](https://github.com/RLBmods/Reseller-Bot/blob/main/resellerapi.png)

> **⚠️ Security Warning:** Treat your API Key like a password. Never share it publicly, commit it to GitHub, or expose it in client-side code (like frontend JavaScript). All API requests should be made securely from your backend server.

---

## 1.2 Create .env file

To ensure that the bot works create a .env file with these parameters

```text
DISCORD_BOT_TOKEN=
RLB_API_KEY=Reseller api key here
ADMIN_ROLE_ID=
ALLOWED_GUILD_ID=
```

## 🌐 2. Base URL & Authentication

**Base URL:**
```text
https://rlbmods.com/api/reseller
```

**Authentication:**
Every request to the API must include your API key in the `Authorization` header as a Bearer token. You must also include the standard JSON headers.

**Required Headers:**
```http
Authorization: Bearer YOUR_API_KEY_HERE
Accept: application/json
Content-Type: application/json
```

---

## 📖 3. API Endpoints

### 💰 Check Wallet Balance
Fetches the current funds available in your reseller wallet.

- **Endpoint:** `GET /balance`
- **Response:**
```json
{
  "success": true,
  "balance": "150.00",
  "currency": "USD"
}
```

### 📦 List Available Products & Pricing
Returns all available products you have permission to resell, along with their pricing durations.

- **Endpoint:** `GET /products`
- **Response:**
```json
{
  "success": true,
  "count": 1,
  "products": [
    {
      "id": 1,
      "name": "Example Product",
      "description": "Product Description",
      "prices": [
        {
          "duration": 1,
          "duration_type": "days",
          "price": "5.00"
        }
      ]
    }
  ]
}
```

### 🟢 Check Product Statuses
Check if a product is currently Undetected, Updating, or Testing. Useful for automatically pausing sales on your store if a product goes into an updating state.

- **Endpoint:** `GET /status`
- **Response:**
```json
{
  "success": true,
  "statuses": [
    {
      "id": 1,
      "name": "Example Product",
      "status": "Undetected",
      "game": "Example Game",
      "updated_at": "2026-06-08 12:00:00"
    }
  ]
}
```

### 🛒 Purchase & Generate Keys
Deducts funds from your balance and generates ready-to-use license keys for your customers.

- **Endpoint:** `POST /keys/create`
- **Body Parameters:**
  - `product` *(string, required)*: The exact name of the product.
  - `duration` *(integer, optional)*: Number for the duration (Default: `1`).
  - `duration_type` *(string, optional)*: Type of duration (e.g., `"days"`, `"months"`) (Default: `"days"`).
  - `count` *(integer, optional)*: Amount of keys to generate (Max: `50`, Default: `1`).

- **Example Request Body:**
```json
{
  "product": "Example Product",
  "duration": 1,
  "duration_type": "days",
  "count": 1
}
```

- **Success Response (201 Created):**
```json
{
  "success": true,
  "message": "Generated 1 license(s) for Example Product",
  "keys": ["XXXX-XXXX-XXXX-XXXX"],
  "cost": "5.00",
  "new_balance": "145.00"
}
```

### 📋 List Purchased Keys
Fetch a history of the keys your workspace has generated.

- **Endpoint:** `GET /keys`
- **Query Parameters (Optional):**
  - `?product=ProductName` - Filter the list by a specific product.
- **Response:**
```json
{
  "success": true,
  "count": 1,
  "licenses": [
    {
      "id": 1234,
      "license_key": "XXXX-XXXX-XXXX-XXXX",
      "product_name": "Example Product",
      "duration": "1 days",
      "status": "active",
      "created_at": "2026-06-08 12:00:00",
      "expires_at": null
    }
  ]
}
```

### 🔄 Reset HWID
Reset the Hardware ID for a specific customer's license key.

- **Endpoint:** `POST /keys/reset`
- **Body Parameters:**
  - `product` *(string, required)*: The exact name of the product.
  - `license_key` *(string, required)*: The key to reset.
- **Example Request Body:**
```json
{
  "product": "Example Product",
  "license_key": "XXXX-XXXX-XXXX-XXXX"
}
```
- **Response:**
```json
{
  "success": true,
  "message": "HWID reset successful"
}
```

### 📜 Activity Logs
View recent API requests made using your API key. (Useful for debugging your bot/store integrations).

- **Endpoint:** `GET /logs`
- **Response:**
```json
{
  "success": true,
  "logs": [
    {
      "id": 1,
      "endpoint": "api/reseller/keys/create",
      "action": "Generate Keys",
      "ip_address": "192.168.1.1",
      "details": {
        "product": "Example Product",
        "count": 1,
        "cost": 5.00
      },
      "created_at": "2026-06-08 12:00:00"
    }
  ]
}
```

---

## 🛠️ Error Handling

If a request fails, the API will return an appropriate HTTP status code (`400`, `401`, `402`, `404`, `500`) and a JSON object containing the error details. 

**Example Error Response (402 Payment Required):**
```json
{
  "success": false,
  "error": {
    "code": 402,
    "message": "Insufficient balance to purchase this license."
  }
}
```

**Common Status Codes:**
- `200 OK`: Request succeeded.
- `201 Created`: Key generation succeeded.
- `400 Bad Request`: Missing parameters or invalid product name.
- `401 Unauthorized`: Invalid or missing API Key.
- `402 Payment Required`: Insufficient reseller wallet balance.
- `404 Not Found`: Product or license key not found.
- `500 Internal Server Error`: An issue occurred on the server.

---

### Support
If you encounter any issues integrating with the API, please open a ticket on your RLBmods dashboard or contact your account manager.
