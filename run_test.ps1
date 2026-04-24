$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginForm = @{ email = "test@example.com"; password = "test" }
try {
    $loginResp = Invoke-WebRequest -Uri "http://127.0.0.1:5000/auth/login" -Method Post -Body $loginForm -WebSession $session
    Write-Host "Login Status: $($loginResp.StatusCode)"
} catch {
    Write-Host "Login Failed: $($_.Exception.Message)"
}

$urls = @("https://www.oecd.org/tax/beps/", "https://www.labuanfsa.gov.my/homepage")
"url,response_status,is_valid,suggestion_type,message_preview" | Out-File -FilePath "test_results.csv" -Encoding utf8

foreach ($url in $urls) {
    try {
        $body = @{ url = $url } | ConvertTo-Json
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/subscriptions/rss/validate" -Method Post -Body $body -ContentType "application/json" -WebSession $session
        $data = $resp.Content | ConvertFrom-Json
        $msg = $data.message -replace '[\r\n,]', ' '
        if ($msg.Length -gt 100) { $msg = $msg.Substring(0, 100) }
        "$url,$($resp.StatusCode),$($data.is_valid),$($data.suggestion_type),$msg" | Out-File -FilePath "test_results.csv" -Append -Encoding utf8
    } catch {
        $stat = "Error"
        if ($_.Exception.Response) { $stat = [int]$_.Exception.Response.StatusCode }
        "$url,$stat,False,N/A,$($_.Exception.Message)" | Out-File -FilePath "test_results.csv" -Append -Encoding utf8
    }
}
