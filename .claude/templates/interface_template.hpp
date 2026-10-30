// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: INTERFACES
/// @file
/// @brief Shared C++ interface header (contract only — no implementation).
/// @author <Name> <email>
//
// Lives ONLY in modules/interfaces (R-IFACE-1). A pure abstract boundary that
// components depend on instead of each other (R-ARCH-1). No algorithm code here.

#pragma once

namespace adas::<domain> {

// Pure interface — abstract methods only, virtual dtor, no state, no I/O.
class I<Name> {
public:
  virtual ~I<Name>() = default;

  virtual void exec(double dtS) = 0;   // cyclic entry point (R-ARCH-4)
  // virtual const <Out>& result() const = 0;
};

}  // namespace adas::<domain>
