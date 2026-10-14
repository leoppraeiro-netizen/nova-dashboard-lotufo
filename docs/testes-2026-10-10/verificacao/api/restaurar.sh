#!/bin/bash
# Para a 8081, restaura o banco limpo e sobe de novo. NUNCA toca dashboard-limpo.db.
cd "/c/Users/<usuario>/Nova Dashboard Lotufo/backend" || exit 1
for p in $(netstat -ano | grep ":8081 " | grep LISTENING | awk '{print $NF}' | sort -u); do taskkill //PID $p //F >/dev/null 2>&1; done
sleep 1
rm -f dados/verif/dashboard.db-wal dados/verif/dashboard.db-shm
cp dados/verif/dashboard-limpo.db dados/verif/dashboard.db
bash "/c/Users/<usuario>/Nova Dashboard Lotufo/docs/testes-2026-10-10/verificacao/api/subir.sh" &
for i in $(seq 1 30); do sleep 1; curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8081/api/health | grep -q 200 && echo "8081 ok" && exit 0; done
echo "8081 nao subiu"; exit 1
