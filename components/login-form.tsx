import { cn } from "cn"

import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"form">) {
  return (
    <form className={cn("flex flex-col gap-6", className)} {...props}>
      <FieldGroup>
        {/* Header */}
        <div className="flex flex-col items-center gap-1 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">
            Inicia sesión
          </h1>
          <p className="max-w-sm text-sm text-balance text-muted-foreground">
            Ingresa tu usuario para acceder a tu cuenta
          </p>
        </div>

        {/* Usuario */}
        <Field>
          <FieldLabel htmlFor="email">Usuario</FieldLabel>
          <Input
            id="email"
            type="text"
            autoComplete="text"
            placeholder="Ingresa usuario"
            required
          />
        </Field>

        {/* Contraseña */}
        <Field>
          <FieldLabel htmlFor="password">Contraseña</FieldLabel>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            placeholder="Ingresa contraseña"
            required
          />
        </Field>

        {/* Botón + link debajo */}
        <Field>
          <Button type="submit" size="lg" className="w-full">
            Acceso
          </Button>
          <FieldDescription className="text-center">
            <a
              href="#"
              className="underline-offset-4 hover:text-foreground hover:underline"
            >
              ¿Olvidaste tu contraseña?
            </a>
          </FieldDescription>
        </Field>
      </FieldGroup>
    </form>
  )
}
