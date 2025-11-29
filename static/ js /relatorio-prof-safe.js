<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Relatório de Ocorrências – PROF-SAFE 24</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        body {
            font-family: Arial, Helvetica, sans-serif;
            background: #05050a;
            color: #f5f5f5;
            padding: 16px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        .card {
            background: #101018;
            border-radius: 14px;
            padding: 18px 16px 20px;
            box-shadow: 0 0 16px rgba(0,0,0,0.7);
        }
        .title { font-size: 20px; font-weight: bold; margin-bottom: 6px; }
        .subtitle { font-size: 13px; color: #bbbbbb; margin-bottom: 14px; }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-top: 10px;
            padding: 9px 16px;
            border-radius: 999px;
            border: none;
            background: #ff8800;
            color: #fff;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
        }
        .btn:hover { background: #e67600; }
        iframe, embed {
            margin-top: 16px;
            width: 100%;
            height: 480px;
            border-radius: 10px;
            border: 1px solid #262638;
        }
    </style>
</head>
<body>
<div class="container">
    <div class="card">
        <div class="title">Relatório de Ocorrências</div>
        <div class="subtitle">
            Abaixo você visualiza o relatório em PDF gerado automaticamente com base nos alertas enviados.
        </div>

        <a class="btn" href="/report.pdf" target="_blank">📄 Abrir em nova aba</a>
        <a class="btn" href="/central">⬅ Voltar para a Central</a>

        <embed src="/report.pdf" type="application/pdf">
    </div>
</div>
</body>
</html>
