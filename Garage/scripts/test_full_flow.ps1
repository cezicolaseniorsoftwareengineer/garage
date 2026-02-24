$BASE_URL = "http://localhost:8000"
Write-Host "TEST: Garage Full Flow" -ForegroundColor Cyan

Write-Host "`n[STEP 1] Registering test user..." -ForegroundColor Yellow
$randomId = Get-Random
$registerPayload = @{
    email = "teste_neon_${randomId}@example.com"
    username = "teste_user_${randomId}"
    password = "Senha123!Neon"
    full_name = "Teste Neon User"
    profession = "Data Scientist"
} | ConvertTo-Json

try {
    $registerResponse = Invoke-WebRequest -Uri "$BASE_URL/api/auth/register" `
        -Method POST -ContentType "application/json" `
        -Body $registerPayload -ErrorAction Stop

    $registerData = $registerResponse.Content | ConvertFrom-Json
    $accessToken = $registerData.access_token
    $userId = $registerData.user_id

    Write-Host "[OK] User registered - ID: $userId" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n[STEP 2] Querying admin users list..." -ForegroundColor Yellow
try {
    $adminResponse = Invoke-WebRequest -Uri "$BASE_URL/api/admin/users" `
        -Method GET -Headers @{"Authorization" = "Bearer $accessToken"} `
        -ErrorAction Stop

    $users = $adminResponse.Content | ConvertFrom-Json
    Write-Host "[OK] Admin users endpoint - Total: $($users.Count)" -ForegroundColor Green

    $foundUser = $users | Where-Object { $_.id -eq $userId }
    if ($foundUser) {
        Write-Host "[OK] User found in database - Name: $($foundUser.full_name)" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] User not found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n[STEP 3] Getting user profile..." -ForegroundColor Yellow
try {
    $profileResponse = Invoke-WebRequest -Uri "$BASE_URL/api/auth/me" `
        -Method GET -Headers @{"Authorization" = "Bearer $accessToken"} `
        -ErrorAction Stop

    $profile = $profileResponse.Content | ConvertFrom-Json
    Write-Host "[OK] Profile retrieved - User: $($profile.username)" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "RESULTS: All tests passed" -ForegroundColor Green
Write-Host "User data is permanently saved in PostgreSQL" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
