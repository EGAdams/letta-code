FROM php:7.4-apache

# Enable mod_rewrite for URL routing
RUN a2enmod rewrite

# Install mysqli extension
RUN docker-php-ext-install mysqli

# Set working directory
WORKDIR /var/www/html

# Copy PHP API code
COPY api/ .

# Remove any problematic .htaccess files from source
RUN find . -name '.htaccess' -delete

# Set permissions
RUN chown -R www-data:www-data /var/www/html

# Enable Apache to serve from subdirectories
RUN echo 'ServerName localhost' >> /etc/apache2/apache2.conf

# Configure Apache for the API - rewrite requests to index.php
RUN echo '<Directory /var/www/html/libraries/local-php-api>' > /etc/apache2/conf-enabled/api-routing.conf && \
    echo '    RewriteEngine On' >> /etc/apache2/conf-enabled/api-routing.conf && \
    echo '    RewriteBase /libraries/local-php-api/' >> /etc/apache2/conf-enabled/api-routing.conf && \
    echo '    RewriteCond %{REQUEST_FILENAME} !-f' >> /etc/apache2/conf-enabled/api-routing.conf && \
    echo '    RewriteCond %{REQUEST_FILENAME} !-d' >> /etc/apache2/conf-enabled/api-routing.conf && \
    echo '    RewriteRule ^(.*)$ index.php/$1 [QSA,L]' >> /etc/apache2/conf-enabled/api-routing.conf && \
    echo '</Directory>' >> /etc/apache2/conf-enabled/api-routing.conf

EXPOSE 80

CMD ["apache2-foreground"]
