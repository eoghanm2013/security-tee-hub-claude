<?php
require __DIR__ . '/../vendor/autoload.php';

use Slim\Factory\AppFactory;
use Psr\Http\Message\ResponseInterface as Response;
use Psr\Http\Message\ServerRequestInterface as Request;

$app = AppFactory::create();
$app->addErrorMiddleware(true, true, true);

$app->get('/', function (Request $request, Response $response) {
    $response->getBody()->write(json_encode(['status' => 'ok', 'tracer' => 'php']));
    return $response->withHeader('Content-Type', 'application/json');
});

$app->get('/search', function (Request $request, Response $response) {
    $q = $request->getQueryParams()['q'] ?? '';
    $results = array_map(fn($i) => "result-$i", range(0, 4));
    $response->getBody()->write(json_encode(['query' => $q, 'results' => $results]));
    return $response->withHeader('Content-Type', 'application/json');
});

$app->post('/login', function (Request $request, Response $response) {
    $body = $request->getParsedBody();
    $username = $body['username'] ?? '';
    $response->getBody()->write(json_encode(['authenticated' => false, 'user' => $username]));
    return $response->withHeader('Content-Type', 'application/json');
});

$app->run();
