FROM php:8.2-apache
RUN apt-get update && apt-get install -y --no-install-recommends \
    unzip curl libzip-dev && \
    docker-php-ext-install zip && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

RUN curl -LO https://github.com/DataDog/dd-trace-php/releases/latest/download/datadog-setup.php && \
    php datadog-setup.php --php-bin=all && \
    rm datadog-setup.php

WORKDIR /var/www/html
COPY composer.json .
RUN composer install --no-dev --optimize-autoloader

COPY public/ public/

RUN echo '<VirtualHost *:80>\n\
    DocumentRoot /var/www/html/public\n\
    <Directory /var/www/html/public>\n\
        AllowOverride All\n\
        Require all granted\n\
        FallbackResource /index.php\n\
    </Directory>\n\
</VirtualHost>' > /etc/apache2/sites-available/000-default.conf && \
    a2enmod rewrite

EXPOSE 80
CMD ["apache2-foreground"]
