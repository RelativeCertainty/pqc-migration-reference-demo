package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const (
	defaultListenAddress   = "127.0.0.1:8080"
	defaultShutdownTimeout = 10 * time.Second
	minimumShutdownTimeout = time.Second
	maximumShutdownTimeout = 60 * time.Second
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := runCLI(ctx, os.Args[1:], os.Stdout, os.Stderr); err != nil {
		if !errors.Is(err, flag.ErrHelp) {
			_, _ = fmt.Fprintln(os.Stderr, err)
		}
		os.Exit(1)
	}
}

func runCLI(ctx context.Context, args []string, stdout, stderr io.Writer) error {
	defaultListen := os.Getenv("PQC_DEMO_LISTEN")
	if defaultListen == "" {
		defaultListen = defaultListenAddress
	}

	flags := flag.NewFlagSet("pqc-reference-demo", flag.ContinueOnError)
	flags.SetOutput(stderr)
	listenAddress := flags.String("listen", defaultListen, "HTTP listen address")
	shutdownTimeout := flags.Duration("shutdown-timeout", defaultShutdownTimeout, "graceful shutdown deadline")
	showVersion := flags.Bool("version", false, "print build identity and exit")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf("unexpected positional arguments")
	}
	if *shutdownTimeout < minimumShutdownTimeout || *shutdownTimeout > maximumShutdownTimeout {
		return fmt.Errorf("shutdown timeout must be between %s and %s", minimumShutdownTimeout, maximumShutdownTimeout)
	}

	ui, err := embeddedUI()
	if err != nil {
		return err
	}
	app, err := newApplication(ui, time.Now)
	if err != nil {
		return fmt.Errorf("initialize portable application: %w", err)
	}
	if *showVersion {
		return writeVersion(stdout, app.assets.manifestDigest)
	}

	listener, err := net.Listen("tcp", *listenAddress)
	if err != nil {
		return fmt.Errorf("start portable listener: %w", err)
	}
	defer listener.Close()

	server := &http.Server{
		Handler:           app,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    16 * 1024,
		ErrorLog:          log.New(io.Discard, "", 0),
	}
	_, _ = fmt.Fprintf(stderr, "pqc-reference-demo listening on %s\n", listener.Addr().String())
	return serveUntilCanceled(ctx, server, listener, *shutdownTimeout)
}

func serveUntilCanceled(
	ctx context.Context,
	server *http.Server,
	listener net.Listener,
	shutdownTimeout time.Duration,
) error {
	serveResult := make(chan error, 1)
	go func() {
		serveResult <- server.Serve(listener)
	}()

	select {
	case err := <-serveResult:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return fmt.Errorf("portable HTTP server stopped: %w", err)
	case <-ctx.Done():
		shutdownContext, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownContext); err != nil {
			_ = server.Close()
			return fmt.Errorf("graceful shutdown: %w", err)
		}
		err := <-serveResult
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			return fmt.Errorf("portable HTTP server stopped during shutdown: %w", err)
		}
		return nil
	}
}
