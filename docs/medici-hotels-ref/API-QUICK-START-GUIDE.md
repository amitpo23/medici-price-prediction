# 🚀 **Quick Start Guide - Medici Hotels API**
**For Third-Party Developers**

---

## ⚡ **5-Minute Integration Setup**

### **1. Base URL**
```
https://[your-medici-domain]
```

### **2. Authentication**
```bash
# Step 1: Get credentials
curl -X POST "https://[domain]/sign-in" \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"password"}'

# Response includes your authorization token
```

### **3. Test Connection**
```bash
# Verify API is working
curl "https://[domain]/healthcheck"
# Response: "Healthy"
```

---

## 🎯 **Most Used Endpoints**

### **🏨 Search Hotels**
```bash
curl -X POST "https://[domain]/Search/Search" \
  -H "Authorization: Basic [your-token]" \
  -H "Content-Type: application/json" \
  -d '{
    "dateFrom": "2026-03-15",
    "dateTo": "2026-03-17",
    "hotelId": 842332
  }'
```

### **📖 Get Bookings**
```bash
curl "https://[domain]/Book/Bookings" \
  -H "Authorization: Basic [your-token]"
```

### **➕ Create Opportunity**
```bash
curl -X POST "https://[domain]/Opportunity/InsertOpp" \
  -H "Authorization: Basic [your-token]" \
  -H "Content-Type: application/json" \
  -d '{
    "hotelId": 842332,
    "startDateStr": "2026-03-15", 
    "endDateStr": "2026-03-17",
    "maxRooms": 5,
    "buyPrice": 200.00,
    "pushPrice": 450.00,
    "reservationFullName": "John Doe"
  }'
```

### **💰 Update Price**
```bash
curl -X POST "https://[domain]/Book/UpdatePrice" \
  -H "Authorization: Basic [your-token]" \
  -H "Content-Type: application/json" \
  -d '{
    "preBookId": 123,
    "pushPrice": 395.00
  }'
```

### **❌ Cancel Booking**
```bash
curl -X DELETE "https://[domain]/Book/CancelBooking?id=123" \
  -H "Authorization: Basic [your-token]"
```

---

## 📊 **Response Examples**

### **Search Results**
```json
{
  "results": [
    {
      "hotelId": 842332,
      "hotelName": "citizenM Miami Brickell",
      "price": {
        "amount": 450.00,
        "currency": "USD"
      },
      "dates": {
        "from": "2026-03-15",
        "to": "2026-03-17"
      },
      "cancellation": {
        "type": "fully-refundable"
      }
    }
  ]
}
```

### **Booking Data**
```json
{
  "bookings": [
    {
      "id": 123,
      "hotelId": 842332,
      "guestName": "John Doe",
      "checkIn": "2026-03-15",
      "checkOut": "2026-03-17",
      "status": "confirmed",
      "price": 450.00
    }
  ]
}
```

---

## ⚠️ **Common Errors**

### **401 - Authentication Failed**
```json
{
  "error": "Invalid credentials",
  "code": 401
}
```
**Fix:** Check your Authorization header format

### **400 - Bad Request**
```json
{
  "error": "Invalid date format",
  "code": 400
}
```
**Fix:** Use YYYY-MM-DD date format

### **404 - Not Found**
```json
{
  "error": "Hotel not found",
  "code": 404
}
```
**Fix:** Verify hotelId exists

---

## 🌐 **Swagger UI (Development)**
```
https://[your-domain]/swagger
```
**Interactive API testing and documentation**

---

## 📞 **Support**
- **Email:** zvi.g@medicihotels.com  
- **Documentation:** [API-DOCUMENTATION-THIRD-PARTY-2026-02-23.md](API-DOCUMENTATION-THIRD-PARTY-2026-02-23.md)