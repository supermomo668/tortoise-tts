response=$(curl "http://127.0.0.1:42110/verify-token" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")
echo $response